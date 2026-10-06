import os, sqlite3, secrets, hashlib
from datetime import datetime, timezone
from flask import Flask, request, jsonify, render_template_string, session, redirect

app=Flask(__name__)
app.secret_key=os.environ.get("ADMIN_SESSION_SECRET", secrets.token_hex(32))
DB=os.environ.get("LICENSE_DB","licenses.db")
ADMIN_PASSWORD=os.environ.get("ADMIN_PASSWORD","change-me")
def db():
    c=sqlite3.connect(DB); c.row_factory=sqlite3.Row
    c.execute("""CREATE TABLE IF NOT EXISTS licenses(
      license_key TEXT PRIMARY KEY, kind TEXT NOT NULL DEFAULT 'lifetime',
      device_hash TEXT, status TEXT NOT NULL DEFAULT 'free',
      created_at TEXT NOT NULL, activated_at TEXT)"""); c.commit(); return c
def make_key():
    return "M6GH-"+"-".join(secrets.token_hex(2).upper() for _ in range(3))
@app.post("/api/activate")
def activate():
    d=request.get_json(silent=True) or {}; key=str(d.get("key","")).strip().upper(); device=str(d.get("device","")).strip()
    if not key or not device:return jsonify(ok=False,error="missing"),400
    dh=hashlib.sha256(device.encode()).hexdigest(); c=db(); row=c.execute("SELECT * FROM licenses WHERE license_key=?",(key,)).fetchone()
    if not row:return jsonify(ok=False,error="invalid_key"),403
    if row["status"]=="blocked":return jsonify(ok=False,error="blocked"),403
    if row["device_hash"] and row["device_hash"]!=dh:return jsonify(ok=False,error="other_device"),403
    if not row["device_hash"]:
        now=datetime.now(timezone.utc).isoformat(); c.execute("UPDATE licenses SET device_hash=?,status='active',activated_at=? WHERE license_key=?",(dh,now,key)); c.commit()
    return jsonify(ok=True,type=row["kind"])
@app.route("/admin",methods=["GET","POST"])
def admin():
    if request.method=="POST" and request.form.get("password")==ADMIN_PASSWORD: session["admin"]=True
    if not session.get("admin"):
        return render_template_string("""<h2>Mazda6GH License Admin</h2><form method=post><input name=password type=password placeholder='Пароль'><button>Войти</button></form>""")
    c=db()
    if request.args.get("new")=="1": c.execute("INSERT INTO licenses(license_key,created_at) VALUES(?,?)",(make_key(),datetime.now(timezone.utc).isoformat())); c.commit(); return redirect("/admin")
    if request.args.get("reset"): c.execute("UPDATE licenses SET device_hash=NULL,status='free',activated_at=NULL WHERE license_key=?",(request.args["reset"],)); c.commit(); return redirect("/admin")
    if request.args.get("block"): c.execute("UPDATE licenses SET status='blocked' WHERE license_key=?",(request.args["block"],)); c.commit(); return redirect("/admin")
    rows=c.execute("SELECT * FROM licenses ORDER BY created_at DESC").fetchall()
    return render_template_string("""<meta name=viewport content='width=device-width'><style>body{font-family:sans-serif;background:#111;color:#eee;padding:18px}a,button{color:#fff;background:#9b1717;padding:8px;text-decoration:none}table{width:100%;margin-top:20px;border-collapse:collapse}td,th{padding:8px;border-bottom:1px solid #444;font-size:13px}</style><h2>Mazda6GH — лицензии</h2><a href='/admin?new=1'>+ Создать Lifetime ключ</a><table><tr><th>Ключ</th><th>Статус</th><th>Активация</th><th>Действия</th></tr>{% for r in rows %}<tr><td>{{r.license_key}}</td><td>{{r.status}}</td><td>{{r.activated_at or '-'}}</td><td><a href='/admin?reset={{r.license_key}}'>Сброс</a> <a href='/admin?block={{r.license_key}}'>Блок</a></td></tr>{% endfor %}</table>""",rows=rows)
if __name__=="__main__": app.run(host="0.0.0.0",port=int(os.environ.get("PORT","8080")))
