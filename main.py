import json, re, hashlib, os
from pathlib import Path
from kivy.app import App
from kivy.core.window import Window
from kivy.metrics import dp
from kivy.properties import StringProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.checkbox import CheckBox
from kivy.uix.filechooser import FileChooserListView
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.tabbedpanel import TabbedPanel, TabbedPanelItem
from kivy.uix.textinput import TextInput
from kivy.uix.gridlayout import GridLayout
from kivy.uix.spinner import Spinner
from kivy.uix.widget import Widget
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.utils import platform
from kivy.core.clipboard import Clipboard
from kivy.graphics import Color, Rectangle

DEFAULT={
 "ui":{"title":"Mazda6GH As-Built TEST/LITE","background":"#f2f2f2","panel":"#fff7f2","width":590,"height":390,"feature_columns":1,"open_text":"Open IC As-Built","save_text":"Save IC As-Built","admin_text":"Админка","author_text":"TEST/LITE","ready_text":"Готово"},
 "username":"admin","password_hash":hashlib.sha256("admin".encode()).hexdigest(),
 "modules":[{"id":"IC","name":"IC: Instrument Cluster","address":"720","version":"TEST"}],
 "rows":[{"module":"IC","address":"720-01-01","value":"2B00 7126 806B","status":"Пример"}],
 "features":[{"id":"new_feature","module":"IC","label":"Новая функция","row":"720-01-01","mode":"HEX","hex_indices":"2,3","on":"40","off":"00","status":"TEST"}]
}

def norm(s): return re.sub(r"[^0-9A-F]","",str(s).upper())
def decode_abt_index(tok):
    tok=tok.upper()
    if len(tok)==2 and tok[0]>="G": return (ord(tok[0])-ord("G"))*16+int(tok[1],16)
    return int(tok,10)
def encode_abt_index(n): n=int(n); return chr(ord("G")+(n>>4))+format(n&15,"X")
def address_parts(addr):
    a,b,c=addr.upper().split("-")
    def cv(x):
        try:return decode_abt_index(x)
        except:return int(x,10)
    return a,cv(b),cv(c)
def checksum_for(addr,raw):
    mod,b,l=address_parts(addr); total=int(mod[:1],16)+int(mod[1:],16)+b+l
    total+=sum(int(raw[i:i+2],16) for i in range(0,len(raw),2)); return f"{total&255:02X}"
def recalc(row):
    raw=norm(row.get("value",""))
    if len(raw)>=4 and len(raw)%2==0:
        raw=raw[:-2]+checksum_for(row["address"],raw[:-2]); row["value"]=" ".join(raw[i:i+4] for i in range(0,len(raw),4))
def parse_indices(spec):
    out=[]
    for p in re.split(r"[,; ]+",str(spec).strip()):
        if not p: continue
        if "-" in p:
            a,b=map(int,p.split("-",1)); out.extend(range(min(a,b),max(a,b)+1))
        else: out.append(int(p))
    return out
def parse_abt(text,modules):
    parsed=[]; by_addr={str(m.get("address","")).upper():m.get("id","IC") for m in modules}; current=None
    for source in text.splitlines():
        line=source.strip().lstrip("﻿")
        bm=re.match(r"^;[ ]*Block[ ]+([0-9]+)",line,re.I)
        if bm: current=int(bm.group(1)); continue
        if not line or line.startswith((";","#","//")): continue
        clean=re.sub(r"[,:=\t]+"," ",line).strip()
        m=(re.match(r"^([0-9A-Fa-f]{3})[- ]?([0-9A-Za-z]{2})[- ]?([0-9A-Za-z]{2})[ ]+([0-9A-Fa-f][0-9A-Fa-f ]*)$",clean)
           or re.match(r"^([0-9A-Fa-f]{3})([0-9A-Za-z]{2})([0-9A-Za-z]{2})([0-9A-Fa-f]+)$",clean))
        if not m: continue
        try: bn=decode_abt_index(m.group(2)); ln=decode_abt_index(m.group(3))
        except: continue
        value=norm(m.group(4))
        if not value or len(value)%2: continue
        addr=f"{m.group(1).upper()}-{bn:02d}-{ln:02d}"
        parsed.append({"module":by_addr.get(m.group(1).upper(),"OTHER"),"address":addr,"value":" ".join(value[i:i+4] for i in range(0,len(value),4)),"status":"Импортировано из ABT","abt_block":current if current is not None else bn})
    return parsed

def module_for_address(addr,modules):
    prefix=str(addr).split("-",1)[0].upper()
    return next((m.get("id") for m in modules if str(m.get("address","")).upper()==prefix),None)

class Main(BoxLayout):
    status=StringProperty("Готово")

class Main(BoxLayout):
    status=StringProperty("Готово")
    def __init__(self,**kw):
        super().__init__(orientation="vertical",spacing=dp(3),padding=(dp(7),dp(28),dp(7),dp(7)),**kw); self.app=App.get_running_app(); self.changed={}; self.changed_positions={}; self.original_values={r.get("address"):norm(r.get("value","")) for r in self.app.data.get("rows",[])}; self.tabs=None; self.pending_save_module=None; self.active_module_id=self.app.data.get("modules",[{"id":"IC"}])[0].get("id","IC"); self.feature_active={}; self.feature_baselines={}; self.row_feature_baselines={}
        self.header=BoxLayout(size_hint_y=None,height=dp(42),spacing=dp(5)); self.title_label=Label(text=self.app.data.get("ui",{}).get("author_text","КТО СДЕЛАЛ ПРОГРАММУ (ИЗМЕНИТЬ)"),font_size="13sp",halign="right"); self.header.add_widget(self.title_label); self.header_links=BoxLayout(size_hint_x=None,width=dp(92),spacing=dp(2)); self.header.add_widget(self.header_links)
        ab=Button(text=self.app.data.get("ui",{}).get("admin_text","⚙"),size_hint_x=None,width=dp(52)); ab.bind(on_release=self.admin_login); self.header.add_widget(ab); self.add_widget(self.header)
        self.tabholder=BoxLayout(); self.add_widget(self.tabholder)
        bar=BoxLayout(size_hint_y=None,height=dp(52),spacing=dp(5)); ui=self.app.data.get("ui",{}); ob=Button(text=ui.get("open_text","Open As-Built file")); sb=Button(text=ui.get("save_text","Save As-Built file")); ob.bind(on_release=self.open_document); sb.bind(on_release=self.save_document); bar.add_widget(ob);bar.add_widget(sb);self.add_widget(bar)
        self.author_bar=BoxLayout(size_hint_y=None,height=dp(1),spacing=dp(1)); self.add_widget(self.author_bar); self.refresh_author()
        self.stat=Label(text=self.status,size_hint_y=None,height=dp(28),font_size="12sp"); self.add_widget(self.stat); self.refresh()
    def set_status(self,s): self.status=s; self.stat.text=s
    def refresh_author(self):
        self.author_bar.clear_widgets(); self.header_links.clear_widgets()
        b=Button(text="Dim304",font_size="10sp",padding=(dp(2),dp(2)))
        b.bind(on_release=lambda _b:self.open_url("https://www.drive2.ru/users/dim304"))
        self.header_links.add_widget(b)
    def open_url(self,url):
        if not url:return
        try:
            if platform=="android":
                from jnius import autoclass
                Intent=autoclass("android.content.Intent"); Uri=autoclass("android.net.Uri"); act=autoclass("org.kivy.android.PythonActivity").mActivity; act.startActivity(Intent(Intent.ACTION_VIEW,Uri.parse(url)))
            else:
                import webbrowser; webbrowser.open(url)
        except Exception as e:self.set_status("Не удалось открыть ссылку: "+str(e))
    def refresh(self):
        keep_tab=self.active_module_id
        self.title_label.text=self.app.data.get("ui",{}).get("author_text","КТО СДЕЛАЛ ПРОГРАММУ (ИЗМЕНИТЬ)"); self.refresh_author(); self.tabholder.clear_widgets(); mods=self.app.data.get("modules",[]); tab_w=min(dp(68),(Window.width-dp(14))/max(1,len(mods))); tabs=TabbedPanel(do_default_tab=False,tab_height=dp(36),tab_width=tab_w); self.tabs=tabs
        for m in self.app.data["modules"]:
            ti=TabbedPanelItem(text=m["id"],font_size="11sp"); ti.bind(on_release=lambda tab:self._remember_tab(tab.text)); scroll=ScrollView(); content=BoxLayout(orientation="vertical",size_hint_y=None,spacing=dp(5),padding=dp(5)); content.bind(minimum_height=content.setter("height"))
            content.add_widget(Label(text=f'[b]{m.get("name")}[/b]  || ID: {m.get("address")} || Ver.: {m.get("version","1")}',markup=True,size_hint_y=None,height=dp(36),halign="left",valign="middle",font_size="12sp",shorten=True,shorten_from="right"))
            feats=[x for x in self.app.data["features"] if x.get("module")==m["id"]]
            if feats:
                cols=max(1,int(self.app.data.get("ui",{}).get("feature_columns",2)))
                grid=GridLayout(cols=cols,size_hint_y=None,spacing=dp(2),row_default_height=dp(38),row_force_default=True)
                grid.bind(minimum_height=grid.setter("height"))
                for f in feats:
                    line=BoxLayout(size_hint_y=None,height=dp(38),spacing=0); cb=CheckBox(size_hint_x=None,width=dp(30)); fk=f.get("id") or (str(f.get("module"))+"|"+str(f.get("row"))+"|"+str(f.get("label"))); cb.active=bool(self.feature_active.get(fk,False)); cb.bind(active=lambda _c,val,ff=f:self.toggle(ff,val)); line.add_widget(cb); lbl=Label(text=f.get("label",""),halign="left",valign="middle",font_size="12sp",padding=(dp(2),0)); lbl.bind(size=lambda inst,val:setattr(inst,"text_size",(val[0],val[1]))); line.add_widget(lbl); grid.add_widget(line)
                content.add_widget(grid)
            
            for r in [x for x in self.app.data["rows"] if x.get("module")==m["id"]]:
                raw=norm(r.get("value","")); pos=self.changed_positions.get(r["address"],set()); rendered=""
                for i,ch in enumerate(raw): rendered += (f'[color=ff3333][b]{ch}[/b][/color]' if i in pos else ch); rendered += (" " if i%4==3 else "")
                addr=r["address"]
                row=GridLayout(cols=2,size_hint_y=None,height=dp(40),spacing=dp(1)); a=Button(text=addr,size_hint_x=.30,font_name="Roboto",font_size="13sp",disabled=True); a.disabled_color=(1,1,1,1); v=Button(text=rendered.strip(),markup=True,size_hint_x=.70,font_name="Roboto",font_size="14sp",disabled=True); v.disabled_color=(1,1,1,1); row.add_widget(a); row.add_widget(v); content.add_widget(row)
            scroll.add_widget(content);ti.add_widget(scroll);tabs.add_widget(ti)
        self.tabholder.add_widget(tabs)
        if keep_tab:
            from kivy.clock import Clock
            Clock.schedule_once(lambda _dt, k=keep_tab: self._restore_tab(k), 0)
    def _remember_tab(self,tab_id):
        self.active_module_id=tab_id
    def _restore_tab(self,tab_id):
        if not self.tabs: return
        target=next((t for t in self.tabs.tab_list if t.text==tab_id),None)
        if target:
            self.tabs.switch_to(target)
            self.active_module_id=tab_id
    def feature_state(self,f):
        r=next((x for x in self.app.data["rows"] if x.get("module")==f.get("module") and x.get("address")==f.get("row")),None)
        if not r:return False
        raw=norm(r.get("value","")); mode=str(f.get("mode","HEX")).upper()
        try:
            if mode=="BITS":
                bi=int(f.get("byte_index",0)); bits=parse_indices(f.get("bits","")); bv=int(raw[bi*2:bi*2+2],16); return bool(bits) and all(bv&(1<<b) for b in bits)
            idx=parse_indices(f.get("hex_indices",0)); target=norm(f.get("on","")); return bool(idx) and len(idx)==len(target) and all(i<len(raw) and raw[i]==target[n] for n,i in enumerate(idx))
        except:return False
    def toggle(self,f,active):
        self.active_module_id=f.get("module",self.active_module_id)
        r=next((x for x in self.app.data["rows"] if x.get("module")==f.get("module") and x.get("address")==f.get("row")),None)
        if not r:return
        fid=f.get("id") or (str(f.get("module"))+"|"+str(f.get("row"))+"|"+str(f.get("label")))
        rowkey=str(f.get("module"))+"|"+str(f.get("row"))
        try:
            if rowkey not in self.row_feature_baselines:self.row_feature_baselines[rowkey]=norm(r.get("value",""))
            self.feature_active[fid]=bool(active)
            baseline=self.row_feature_baselines[rowkey]
            arr=list(baseline)
            active_features=[]
            for ff in self.app.data.get("features",[]):
                ffid=ff.get("id") or (str(ff.get("module"))+"|"+str(ff.get("row"))+"|"+str(ff.get("label")))
                if ff.get("module")==f.get("module") and ff.get("row")==f.get("row") and self.feature_active.get(ffid,False):active_features.append(ff)
            for ff in active_features:
                mode=str(ff.get("mode","HEX")).upper()
                if mode=="BITS":
                    bi=int(ff.get("byte_index",0)); bits=parse_indices(ff.get("bits",""))
                    if bi*2+2>len(arr):raise ValueError(f"Byte {bi} вне строки {r.get('address')}")
                    old=int("".join(arr[bi*2:bi*2+2]),16); new=old
                    for b in bits:new|=(1<<b)
                    arr[bi*2:bi*2+2]=list(f"{new:02X}")
                else:
                    idx=parse_indices(ff.get("hex_indices",0)); target=norm(ff.get("on",""))
                    if len(target)!=len(idx):raise ValueError("количество HEX индексов не совпадает со значением")
                    for n,i in enumerate(idx):
                        if i>=len(arr):raise ValueError(f"HEX индекс {i} вне строки {r.get('address')}")
                        arr[i]=target[n]
            if active_features:
                r["value"]=" ".join("".join(arr)[i:i+4] for i in range(0,len(arr),4)); recalc(r)
            else:
                r["value"]=" ".join(baseline[i:i+4] for i in range(0,len(baseline),4))
            final=norm(r["value"]); live={i for i in range(min(len(baseline),len(final))) if baseline[i]!=final[i]}
            self.changed_positions[r["address"]]=live; self.changed[r["address"]]=bool(live)
            self.set_status(f'{f.get("label")}: изменено' if live else f'{f.get("label")}: исходное значение')
            self.refresh()
        except Exception as e:
            self.feature_active[fid]=not bool(active)
            self.set_status("Ошибка параметра: "+str(e))
    def open_document(self,*_):
        if platform == "android":
            try:
                from android import activity
                from jnius import autoclass
                Intent=autoclass("android.content.Intent"); self._android_activity=activity; activity.bind(on_activity_result=self._on_open_result); intent=Intent(Intent.ACTION_OPEN_DOCUMENT); intent.addCategory(Intent.CATEGORY_OPENABLE); intent.setType("*/*"); autoclass("org.kivy.android.PythonActivity").mActivity.startActivityForResult(intent,4101); self.set_status("Выберите .abt файл")
            except Exception as e:self.set_status("Android picker: "+str(e))
        else:self.open_picker()
    def save_document(self,*_):
        if platform == "android":
            try:
                from android import activity
                from jnius import autoclass
                Intent=autoclass("android.content.Intent"); self._android_activity=activity; activity.bind(on_activity_result=self._on_save_result); self.pending_save_module=self.current_module(); intent=Intent(Intent.ACTION_CREATE_DOCUMENT); intent.addCategory(Intent.CATEGORY_OPENABLE); intent.setType("application/octet-stream"); intent.putExtra(Intent.EXTRA_TITLE,self.pending_save_module["id"]+".abt"); autoclass("org.kivy.android.PythonActivity").mActivity.startActivityForResult(intent,4102); self.set_status("Выберите место сохранения")
            except Exception as e:self.set_status("Android save picker: "+str(e))
        else:self.save_picker()
    def _read_android_uri(self,uri):
        from jnius import autoclass
        act=autoclass("org.kivy.android.PythonActivity").mActivity
        stream=act.getContentResolver().openInputStream(uri)
        InputStreamReader=autoclass("java.io.InputStreamReader"); BufferedReader=autoclass("java.io.BufferedReader")
        br=BufferedReader(InputStreamReader(stream,"UTF-8")); lines=[]
        try:
            while True:
                line=br.readLine()
                if line is None: break
                lines.append(str(line))
        finally:
            br.close()
        return "\n".join(lines)
    def _write_android_uri(self,uri,data):
        from jnius import autoclass
        act=autoclass("org.kivy.android.PythonActivity").mActivity
        stream=act.getContentResolver().openOutputStream(uri,"w")
        try:
            ByteBuffer=autoclass("java.nio.ByteBuffer")
            jbytes=ByteBuffer.wrap(data).array()
            stream.write(jbytes)
            stream.flush()
        finally:
            stream.close()
    def _on_open_result(self,requestCode,resultCode,intent):
        if requestCode!=4101:return
        try:

            if getattr(self,"_android_activity",None):
                self._android_activity.unbind(on_activity_result=self._on_open_result)
            if intent is None:return
            raw_text=self._read_android_uri(intent.getData())
            parsed=parse_abt(raw_text,self.app.data["modules"])
            if not parsed:self.set_status("ABT файл не распознан");return
            selected=self.current_module(); selected_id=selected.get("id"); selected_addr=str(selected.get("address","")).upper()
            file_addrs={str(r.get("address","")).split("-",1)[0].upper() for r in parsed}
            if file_addrs!={selected_addr}:
                names=[m.get("id") for m in self.app.data["modules"] if str(m.get("address","")).upper() in file_addrs]
                detected=", ".join(names) if names else ", ".join(sorted(file_addrs))
                self.set_status(f"Ошибка: выбран {selected_id}, файл относится к {detected}");return
            existing={(r.get("module"),r.get("address")):r for r in self.app.data["rows"]}
            for r in parsed:
                r["module"]=selected_id
                existing[(selected_id,r["address"])]=r
            self.app.data["rows"]=list(existing.values()); self.changed={}; self.changed_positions={}; self.feature_active={}; self.row_feature_baselines={}; self.original_values={r.get("address"):norm(r.get("value","")) for r in self.app.data["rows"]}
            self.app.save_settings()
            from kivy.clock import Clock
            Clock.schedule_once(lambda _dt,n=len(parsed): (self.refresh(),self.set_status(f"Открыто строк: {n}")),0)
        except Exception as e:self.set_status("Ошибка открытия: "+str(e))
    def _module_abt_bytes(self,m):
        rows=[r for r in self.app.data["rows"] if r.get("module")==m["id"] and r.get("value","").strip()]
        grouped={}
        for r in rows:
            mod,b,l=address_parts(r["address"]); grouped.setdefault(int(r.get("abt_block",b)),[]).append((l,r,mod,b))
        lines=[]
        for block in sorted(grouped):
            lines.append(f";Block {block}")
            for _,r,mod,b in sorted(grouped[block]):
                recalc(r); _,_,l=address_parts(r["address"])
                lines.append(f"{mod}{encode_abt_index(b)}{encode_abt_index(l)}{norm(r['value'])}")
        return ("\r\n".join(lines)+"\r\n").encode("ascii")
    def _on_save_result(self,requestCode,resultCode,intent):
        if requestCode!=4102:return
        try:
            if getattr(self,"_android_activity",None):
                self._android_activity.unbind(on_activity_result=self._on_save_result)
            if intent is None:return
            data=self._module_abt_bytes(self.pending_save_module or self.current_module())
            self._write_android_uri(intent.getData(),data); self.set_status("ABT сохранён")
        except Exception as e:self.set_status("Ошибка сохранения: "+str(e))

    def picker(self,title,save=False):
        root=BoxLayout(orientation="vertical")
        fc=FileChooserListView(path=str(Path.home()),filters=["*.abt","*.ABT","*.txt"] if not save else [])
        root.add_widget(fc)
        if save:
            name=TextInput(text="IC.abt",multiline=False,size_hint_y=None,height=dp(44)); root.add_widget(name)
        buttons=BoxLayout(size_hint_y=None,height=dp(48))
        ok=Button(text="Сохранить" if save else "Открыть"); cancel=Button(text="Отмена")
        buttons.add_widget(ok);buttons.add_widget(cancel);root.add_widget(buttons)
        pop=Popup(title=title,content=root,size_hint=(.96,.92));cancel.bind(on_release=pop.dismiss)
        if save: ok.bind(on_release=lambda *_:self.do_save(fc.path,name.text,pop))
        else: ok.bind(on_release=lambda *_:self.do_open(fc.selection,pop))
        pop.open()
    def open_picker(self,*_):self.picker("Открыть As-Built")
    def save_picker(self,*_):self.picker("Сохранить As-Built",True)
    def do_open(self,selection,pop):
        if not selection:return
        try:
            parsed=parse_abt(Path(selection[0]).read_text(encoding="utf-8-sig",errors="replace"),self.app.data["modules"])
            if not parsed:self.set_status("ABT строки не распознаны");return
            existing={(r.get("module"),r.get("address")):r for r in self.app.data["rows"]}
            for r in parsed:existing[(r["module"],r["address"])]=r
            self.app.data["rows"]=list(existing.values());self.changed={};self.changed_positions={};self.feature_active={};self.row_feature_baselines={};self.original_values={r.get("address"):norm(r.get("value","")) for r in self.app.data["rows"]}
            self.app.save_settings();pop.dismiss();self.refresh();self.set_status(f"Открыто строк: {len(parsed)}")
        except Exception as e:self.set_status(str(e))
    def current_module(self):
        if not self.tabs or not self.tabs.current_tab:return self.app.data["modules"][0]
        mid=self.tabs.current_tab.text
        return next((m for m in self.app.data["modules"] if m["id"]==mid),self.app.data["modules"][0])
    def do_save(self,folder,name,pop):
        try:
            p=Path(folder)/(name if name.lower().endswith(".abt") else name+".abt")
            p.write_bytes(self._module_abt_bytes(self.current_module()));pop.dismiss();self.set_status(f"Сохранено: {p.name}")
        except Exception as e:self.set_status("Ошибка сохранения: "+str(e))

    def admin_login(self,*_):
        box=BoxLayout(orientation="vertical",spacing=dp(4),padding=dp(8))
        u=TextInput(hint_text="Логин",multiline=False,size_hint_y=None,height=dp(38),size_hint_x=.72,pos_hint={"center_x":.5})
        p=TextInput(hint_text="Пароль",password=True,multiline=False,size_hint_y=None,height=dp(38),size_hint_x=.72,pos_hint={"center_x":.5})
        b=Button(text="Войти",size_hint_y=None,height=dp(40),size_hint_x=.55,pos_hint={"center_x":.5})
        box.add_widget(u);box.add_widget(p);box.add_widget(b)
        pop=Popup(title="Администратор",content=box,size_hint=(.72,.34))
        def go(*_):
            digest=hashlib.sha256(p.text.encode()).hexdigest()
            if u.text==self.app.data["username"] and digest==self.app.data["password_hash"]:
                pop.dismiss();self.admin_panel()
            else:self.set_status("Неверный логин или пароль")
        b.bind(on_release=go);pop.open()
    def admin_panel(self):
        f=self.app.data["features"][0]
        root=BoxLayout(orientation="vertical",spacing=dp(5),padding=dp(8))
        fields={}
        for key,label in [("label","Название функции"),("row","Строка"),("hex_indices","HEX индексы"),("on","ВКЛ"),("off","ВЫКЛ")]:
            root.add_widget(Label(text=label,size_hint_y=None,height=dp(25),font_size="11sp"))
            ed=TextInput(text=str(f.get(key,"")),multiline=False,size_hint_y=None,height=dp(38)); fields[key]=ed; root.add_widget(ed)
        buttons=BoxLayout(size_hint_y=None,height=dp(42),spacing=dp(4))
        save=Button(text="Сохранить"); close=Button(text="Закрыть"); buttons.add_widget(save); buttons.add_widget(close); root.add_widget(buttons)
        pop=Popup(title="Админка TEST/LITE",content=root,size_hint=(.82,.70)); close.bind(on_release=pop.dismiss)
        def apply(*_):
            try:
                for k,ed in fields.items(): f[k]=ed.text.strip()
                self.app.save_settings(); self.refresh(); self.set_status("Тестовый параметр сохранён"); pop.dismiss()
            except Exception as ex:self.set_status("Ошибка: "+str(ex))
        save.bind(on_release=apply); pop.open()

class MazdaAndroidApp(App):
    def build(self):
        self.title="Mazda6GH As-Built TEST/LITE"
        Window.softinput_mode="below_target"
        self.db=Path(self.user_data_dir)/"settings.json"
        self.data=self.load_settings()
        return Main()
    def load_settings(self):
        try:
            if self.db.exists():
                data=json.loads(self.db.read_text(encoding="utf-8"))
                data["username"]="admin"; data["password_hash"]=hashlib.sha256("admin".encode()).hexdigest()
                for k in ("link1_text","link1_url","link2_text","link2_url"): data.setdefault("ui",{}).pop(k,None)
                return data
        except:pass
        return json.loads(json.dumps(DEFAULT,ensure_ascii=False))
    def save_settings(self):
        self.db.parent.mkdir(parents=True,exist_ok=True)
        self.db.write_text(json.dumps(self.data,ensure_ascii=False,indent=2),encoding="utf-8")

if __name__=="__main__":
    MazdaAndroidApp().run()


# V2.5 admin panel is assembled in part3c.
