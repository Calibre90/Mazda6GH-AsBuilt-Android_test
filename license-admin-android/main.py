import base64, csv, json
from datetime import datetime, timezone
from pathlib import Path
from kivy.app import App
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.scrollview import ScrollView
from kivy.core.clipboard import Clipboard
from kivy.utils import platform
from kivy.clock import Clock

class LicenseAdmin(App):
    def build(self):
        self.title="Mazda6GH License Admin"
        self.data_dir=Path(self.user_data_dir)
        self.keyfile=self.data_dir/"owner_private.pem"
        self.logfile=self.data_dir/"issued_licenses.csv"
        root=BoxLayout(orientation="vertical",padding=dp(10),spacing=dp(7))
        root.add_widget(Label(text="[b]Mazda6GH LICENSE ADMIN[/b]",markup=True,size_hint_y=None,height=dp(42),font_size="18sp"))
        self.device=TextInput(hint_text="Device ID (16 HEX)",multiline=False,size_hint_y=None,height=dp(44))
        self.customer=TextInput(hint_text="Покупатель / имя",multiline=False,size_hint_y=None,height=dp(44))
        self.note=TextInput(hint_text="Примечание",multiline=False,size_hint_y=None,height=dp(44))
        root.add_widget(self.device);root.add_widget(self.customer);root.add_widget(self.note)
        # Owner-only setup: select PEM from Android files or paste manually.
        if not self.keyfile.exists():
            self.pem_input=TextInput(hint_text="Вставьте весь текст PEM здесь или выберите файл ниже",multiline=True,size_hint_y=None,height=dp(125))
            root.add_widget(self.pem_input)
            choose=Button(text="ВЫБРАТЬ ФАЙЛ PEM",size_hint_y=None,height=dp(44))
            choose.bind(on_release=self.choose_pem_file)
            root.add_widget(choose)
            install=Button(text="УСТАНОВИТЬ ПРИВАТНЫЙ КЛЮЧ",size_hint_y=None,height=dp(44))
            install.bind(on_release=self.install_private_key)
            root.add_widget(install)
        b=Button(text="СОЗДАТЬ LIFETIME",size_hint_y=None,height=dp(48));b.bind(on_release=self.generate);root.add_widget(b)
        self.out=TextInput(readonly=True,hint_text="Здесь появится Lifetime ключ",size_hint_y=None,height=dp(130));root.add_widget(self.out)
        row=BoxLayout(size_hint_y=None,height=dp(44),spacing=dp(5))
        cp=Button(text="КОПИРОВАТЬ");cp.bind(on_release=lambda *_:Clipboard.copy(self.out.text))
        vr=Button(text="ПРОВЕРИТЬ");vr.bind(on_release=self.verify_format)
        row.add_widget(cp);row.add_widget(vr);root.add_widget(row)
        self.status=Label(text="Приватный ключ: "+("установлен" if self.keyfile.exists() else "НЕ УСТАНОВЛЕН"),size_hint_y=None,height=dp(34),font_size="11sp");root.add_widget(self.status)
        self.history=Label(text=self.history_text(),markup=True,size_hint_y=None)
        self.history.bind(texture_size=lambda w,s:setattr(w,"height",s[1]))
        sc=ScrollView();sc.add_widget(self.history);root.add_widget(sc)
        return root
    def choose_pem_file(self,*_):
        if platform!="android":
            self.status.text="Выбор файла доступен на Android"
            return
        try:
            from jnius import autoclass
            PythonActivity=autoclass("org.kivy.android.PythonActivity")
            Intent=autoclass("android.content.Intent")
            self._pem_request_code=8421
            activity=PythonActivity.mActivity
            from android import activity as android_activity
            android_activity.bind(on_activity_result=self._pem_file_result)
            intent=Intent(Intent.ACTION_OPEN_DOCUMENT)
            intent.addCategory(Intent.CATEGORY_OPENABLE)
            intent.setType("*/*")
            activity.startActivityForResult(intent,self._pem_request_code)
        except Exception as e:
            error=str(e)
            Clock.schedule_once(lambda dt,error=error:setattr(self.status,"text","Ошибка выбора файла: "+error),0)

    def _pem_file_result(self,request_code,result_code,intent):
        if request_code!=getattr(self,"_pem_request_code",8421):return
        try:
            from android import activity as android_activity
            android_activity.unbind(on_activity_result=self._pem_file_result)
            if result_code!= -1 or intent is None:return
            uri=intent.getData()
            from jnius import autoclass
            PythonActivity=autoclass("org.kivy.android.PythonActivity")
            InputStreamReader=autoclass("java.io.InputStreamReader")
            BufferedReader=autoclass("java.io.BufferedReader")
            stream=PythonActivity.mActivity.getContentResolver().openInputStream(uri)
            reader=BufferedReader(InputStreamReader(stream,"UTF-8"))
            lines=[]
            try:
                while len(lines)<100:
                    line=reader.readLine()
                    if line is None:break
                    lines.append(str(line))
            finally:
                reader.close()
            pem="\n".join(lines).strip()
            if len(pem)>16384:raise ValueError("Слишком большой PEM")
            # Android activity callbacks may run outside Kivy's UI thread.
            # Never assign widget properties from this callback.
            Clock.schedule_once(lambda dt,pem=pem:self._apply_selected_pem(pem),0)
        except Exception as e:
            error=str(e)
            Clock.schedule_once(lambda dt,error=error:setattr(self.status,"text","Ошибка чтения PEM: "+error),0)

    def _apply_selected_pem(self,pem):
        self.pem_input.text=pem
        self.status.text="PEM загружен. Нажмите УСТАНОВИТЬ ПРИВАТНЫЙ КЛЮЧ."

    def install_private_key(self,*_):
        try:
            pem=self.pem_input.text.strip()
            if not pem:
                raise ValueError("Сначала выберите PEM-файл или вставьте его текст")
            if "-----BEGIN RSA PRIVATE KEY-----" in pem:
                raise ValueError("Это PKCS#1 (RSA PRIVATE KEY). Нужен PKCS#8 (BEGIN PRIVATE KEY). Конвертируйте через openssl pkcs8 -topk8 -nocrypt")
            if "-----BEGIN PRIVATE KEY-----" not in pem or "-----END PRIVATE KEY-----" not in pem:
                raise ValueError("Ожидается полный PEM PKCS#8 с BEGIN PRIVATE KEY и END PRIVATE KEY")
            from jnius import autoclass
            Base64=autoclass("android.util.Base64")
            KeyFactory=autoclass("java.security.KeyFactory")
            PKCS8=autoclass("java.security.spec.PKCS8EncodedKeySpec")
            body="".join(line.strip() for line in pem.splitlines() if not line.startswith("-----"))
            raw=Base64.decode(body,Base64.DEFAULT)
            KeyFactory.getInstance("RSA").generatePrivate(PKCS8(raw))
            self.data_dir.mkdir(parents=True, exist_ok=True)
            self.keyfile.write_text(pem+"\n",encoding="ascii")
            self.pem_input.text=""
            self.status.text="Приватный RSA-ключ установлен. Можно выдавать лицензии."
        except Exception as e:
            self.status.text="Ошибка установки ключа: "+str(e)
    def b64(self,b):return base64.urlsafe_b64encode(b).decode().rstrip("=")
    def normalize_device(self,s):
        d="".join(ch for ch in s.upper() if ch in "0123456789ABCDEF")
        if len(d)!=16:raise ValueError("Device ID должен содержать 16 HEX-символов")
        return d
    def _java_sign(self,message):
        if platform!="android":raise ValueError("Подпись доступна только в Android Admin")
        if not self.keyfile.exists():raise ValueError("Приватный мастер-ключ не установлен")
        from jnius import autoclass
        Base64=autoclass("android.util.Base64")
        KeyFactory=autoclass("java.security.KeyFactory")
        Signature=autoclass("java.security.Signature")
        PKCS8=autoclass("java.security.spec.PKCS8EncodedKeySpec")
        pem=self.keyfile.read_text(encoding="ascii")
        body="".join(x.strip() for x in pem.splitlines() if not x.startswith("-----"))
        raw=Base64.decode(body,Base64.DEFAULT)
        private=KeyFactory.getInstance("RSA").generatePrivate(PKCS8(raw))
        signer=Signature.getInstance("SHA256withRSA")
        signer.initSign(private)
        signer.update(message.encode("ascii"))
        return bytes(signer.sign())
    def generate(self,*_):
        try:
            dev=self.normalize_device(self.device.text)
            payload={"device":dev,"type":"lifetime","v":1}
            p=self.b64(json.dumps(payload,separators=(",",":"),sort_keys=True).encode())
            code="M6L1."+p+"."+self.b64(self._java_sign(p))
            self.out.text=code
            new=not self.logfile.exists()
            with self.logfile.open("a",newline="",encoding="utf-8-sig") as f:
                w=csv.writer(f)
                if new:w.writerow(["created_utc","device_id","customer","note","license"])
                w.writerow([datetime.now(timezone.utc).isoformat(),dev,self.customer.text.strip(),self.note.text.strip(),code])
            self.status.text="Lifetime создан и записан в журнал";self.history.text=self.history_text()
        except Exception as e:self.status.text="Ошибка: "+str(e)
    def verify_format(self,*_):
        try:
            code="".join(self.out.text.split());parts=code.split(".")
            if len(parts)!=3 or parts[0]!="M6L1":raise ValueError("Неверный формат")
            pad="="*((4-len(parts[1])%4)%4);d=json.loads(base64.urlsafe_b64decode(parts[1]+pad))
            self.status.text=f"Ключ: {d.get('type')} • Device {d.get('device')}"
        except Exception as e:self.status.text="Ошибка ключа: "+str(e)
    def history_text(self):
        if not self.logfile.exists():return "[b]История:[/b]\nПока лицензий нет"
        try:
            rows=list(csv.DictReader(self.logfile.open(encoding="utf-8-sig")))[-30:][::-1]
            return "[b]Последние лицензии:[/b]\n"+"\n".join(f"{r['created_utc'][:10]}  {r['device_id']}  {r['customer']}" for r in rows)
        except:return "[b]История:[/b] ошибка чтения"

if __name__=="__main__":LicenseAdmin().run()
