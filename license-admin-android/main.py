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
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.gridlayout import GridLayout
from kivy.utils import escape_markup
from kivy.core.window import Window

class LicenseAdmin(App):
    def build(self):
        self.title="Mazda6GH License Admin"

        self.data_dir=Path(self.user_data_dir)
        self.keyfile=self.data_dir/"owner_private.pem"
        self.logfile=self.data_dir/"issued_licenses.csv"
        root=BoxLayout(orientation="vertical",padding=dp(10),spacing=dp(7))
        root.add_widget(Label(text="[b]Mazda6GH LICENSE ADMIN[/b]",markup=True,size_hint_y=None,height=dp(42),font_size="18sp"))
        self.device=TextInput(hint_text="Device ID (16 HEX)",multiline=False,size_hint_y=None,height=dp(44))
        self.customer=TextInput(hint_text="Email покупателя",multiline=False,size_hint_y=None,height=dp(44))
        self.note=TextInput(hint_text="Примечание / имя",multiline=False,size_hint_y=None,height=dp(44))
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
        self.out.bind(on_touch_up=self.clear_output_selection)
        row=BoxLayout(size_hint_y=None,height=dp(44),spacing=dp(5))
        cp=Button(text="КОПИРОВАТЬ");cp.bind(on_release=lambda *_:self.copy_license(self.out.text))
        vr=Button(text="ПРОВЕРИТЬ");vr.bind(on_release=self.verify_format)
        row.add_widget(cp);row.add_widget(vr);root.add_widget(row)
        self.status=Label(text="Приватный ключ: "+("установлен" if self.keyfile.exists() else "НЕ УСТАНОВЛЕН"),size_hint_y=None,height=dp(34),font_size="11sp");root.add_widget(self.status)
        journal=Button(text="ЖУРНАЛ ЛИЦЕНЗИЙ",size_hint_y=None,height=dp(48))
        journal.bind(on_release=self.open_journal)
        root.add_widget(journal)
        self.manager=ScreenManager()
        if platform=="android":
            Window.bind(on_keyboard=self.on_android_back)
        main=Screen(name="main");main.add_widget(root)
        journal_screen=Screen(name="journal")
        panel=BoxLayout(orientation="vertical",padding=[dp(10),dp(42),dp(10),dp(10)],spacing=dp(8))
        head=BoxLayout(size_hint_y=None,height=dp(48),spacing=dp(8))
        back=Button(text="НАЗАД",size_hint_x=.28)
        back.bind(on_release=lambda *_:setattr(self.manager,"current","main"))
        head.add_widget(back)
        head.add_widget(Label(text="[b]ЖУРНАЛ ЛИЦЕНЗИЙ[/b]",markup=True))
        panel.add_widget(head)
        self.search=TextInput(hint_text="Поиск: email, имя, Device ID, ключ",multiline=False,size_hint_y=None,height=dp(48))
        self.search.bind(text=lambda *_:self.refresh_journal())
        panel.add_widget(self.search)
        self.journal_count=Label(size_hint_y=None,height=dp(30),font_size="13sp")
        panel.add_widget(self.journal_count)
        export=Button(text="ЭКСПОРТ ВСЕГО ЖУРНАЛА (CSV)",size_hint_y=None,height=dp(46))
        export.bind(on_release=self.export_journal)
        panel.add_widget(export)
        sc=ScrollView(do_scroll_x=False)
        self.journal_rows=GridLayout(cols=1,spacing=dp(7),size_hint_y=None)
        self.journal_rows.bind(minimum_height=self.journal_rows.setter("height"))
        sc.add_widget(self.journal_rows);panel.add_widget(sc)
        journal_screen.add_widget(panel)
        self.manager.add_widget(main);self.manager.add_widget(journal_screen)
        return self.manager
    def clear_output_selection(self,widget,touch):
        if widget.collide_point(*touch.pos):
            Clock.schedule_once(lambda dt:self._reset_output_selection(),0.1)
        return False
    def _reset_output_selection(self):
        try:
            self.out.cancel_selection()
            self.out.select_text(0,0)
            self.out.focus=False
        except Exception:
            pass
    def copy_license(self,code):
        code="".join(str(code).split())
        if not code:
            self.status.text="Нет лицензии для копирования"
            return
        try:
            if platform=="android":
                from jnius import autoclass
                activity=autoclass("org.kivy.android.PythonActivity").mActivity
                Context=autoclass("android.content.Context")
                ClipData=autoclass("android.content.ClipData")
                manager=activity.getSystemService(Context.CLIPBOARD_SERVICE)
                manager.setPrimaryClip(ClipData.newPlainText("Mazda6GH License",code))
            else:
                Clipboard.copy(code)
            self.status.text="Лицензия скопирована"
            if self.manager.current=="journal":
                self.journal_count.text="Лицензия скопирована в буфер обмена"
            self._reset_output_selection()
        except Exception as e:
            self.status.text="Ошибка копирования: "+str(e)
            if self.manager.current=="journal":
                self.journal_count.text="Ошибка копирования: "+str(e)
    def on_android_back(self,window,key,*args):
        if key==27 and self.manager.current=="journal":
            self.manager.current="main"
            return True
        return False
    def export_journal(self,*_):
        try:
            rows=self.read_journal()
            if not rows:
                self.journal_count.text="Журнал пуст — экспортировать нечего"
                return
            self.data_dir.mkdir(parents=True,exist_ok=True)
            name="licenses_export_"+datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")+".csv"
            target=self.data_dir/name
            with target.open("w",newline="",encoding="utf-8-sig") as f:
                writer=csv.writer(f)
                writer.writerow(["Дата UTC","Device ID","Email","Примечание / имя","Лицензия"])
                for row in rows:
                    writer.writerow([row.get("created_utc",""),row.get("device_id",""),row.get("customer",""),row.get("note",""),row.get("license","")])
            if platform=="android":
                from jnius import autoclass
                from android import activity as android_activity
                Intent=autoclass("android.content.Intent")
                self._export_file=target
                self._export_request_code=8422
                android_activity.bind(on_activity_result=self._export_result)
                intent=Intent(Intent.ACTION_CREATE_DOCUMENT)
                intent.addCategory(Intent.CATEGORY_OPENABLE)
                intent.setType("text/csv")
                intent.putExtra(Intent.EXTRA_TITLE,name)
                autoclass("org.kivy.android.PythonActivity").mActivity.startActivityForResult(intent,self._export_request_code)
                self.journal_count.text="Выберите место сохранения CSV"
            else:
                self.journal_count.text="Экспорт: "+str(target)
        except Exception as e:
            self.journal_count.text="Ошибка экспорта: "+str(e)
    def _export_result(self,request_code,result_code,intent):
        if request_code!=getattr(self,"_export_request_code",8422):return
        from android import activity as android_activity
        android_activity.unbind(on_activity_result=self._export_result)
        if result_code!=-1 or intent is None:
            Clock.schedule_once(lambda dt:setattr(self.journal_count,"text","Экспорт отменён"),0)
            return
        try:
            from jnius import autoclass
            activity=autoclass("org.kivy.android.PythonActivity").mActivity
            stream=activity.getContentResolver().openOutputStream(intent.getData())
            try:
                payload=self._export_file.read_bytes()
                # Write through Android OutputStream; avoid unsupported jnius.jarray import.
                for value in payload:
                    stream.write(int(value))
                stream.flush()
            finally:
                stream.close()
            Clock.schedule_once(lambda dt:setattr(self.journal_count,"text","CSV успешно сохранён"),0)
        except Exception as e:
            error=str(e)
            Clock.schedule_once(lambda dt,error=error:setattr(self.journal_count,"text","Ошибка записи CSV: "+error),0)

    def open_journal(self,*_):
        self.refresh_journal()
        self._reset_output_selection()
        self.manager.current="journal"
    def read_journal(self):
        if not self.logfile.exists():return []
        with self.logfile.open("r",newline="",encoding="utf-8-sig") as f:
            return list(csv.DictReader(f))
    def refresh_journal(self):
        self.journal_rows.clear_widgets()
        try:
            rows=self.read_journal()
            query=self.search.text.strip().casefold()
            if query:
                rows=[r for r in rows if any(query in str(r.get(k,"")).casefold() for k in ("created_utc","device_id","customer","note","license"))]
            self.journal_count.text=f"Найдено: {len(rows)}"
            if not rows:
                self.journal_rows.add_widget(Label(text="Записей нет",size_hint_y=None,height=dp(60)))
            for r in reversed(rows):
                card=BoxLayout(orientation="vertical",size_hint_y=None,height=dp(172),spacing=dp(3))
                date=str(r.get("created_utc",""))[:19].replace("T"," ")
                mail=escape_markup(str(r.get("customer","")))
                note=escape_markup(str(r.get("note","")))
                dev=escape_markup(str(r.get("device_id","")))
                summary=Label(text=f"[b]{mail}[/b]\n{note}\nDevice ID: {dev}\nДата (UTC): {date}",markup=True,halign="left",valign="middle",size_hint_y=None,height=dp(118))
                summary.bind(size=lambda w,_:setattr(w,"text_size",(w.width,None)))
                card.add_widget(summary)
                copy=Button(text="КОПИРОВАТЬ ЛИЦЕНЗИЮ",size_hint_y=None,height=dp(45))
                license_code=str(r.get("license",""))
                copy.bind(on_release=lambda _,code=license_code:self.copy_license(code))
                card.add_widget(copy)
                self.journal_rows.add_widget(card)
        except Exception as e:
            self.journal_count.text="Ошибка чтения журнала: "+str(e)
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
            self.status.text="Lifetime создан и записан в журнал"
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
