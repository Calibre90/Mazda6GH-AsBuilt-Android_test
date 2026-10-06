"""Mazda6GH Offline Lifetime License Generator — Run #22.
PRIVATE KEY IS NEVER STORED IN THIS REPOSITORY.
Place Mazda6GH-Run22-LICENSE-PRIVATE.pem next to this script.
Requires: pip install cryptography
"""
import base64, json, csv, sys
from pathlib import Path
from datetime import datetime, timezone
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

HERE=Path(__file__).resolve().parent
KEYFILE=HERE/"Mazda6GH-Run22-LICENSE-PRIVATE.pem"
LOGFILE=HERE/"issued_licenses.csv"

def b64(data:bytes)->str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")

def normalize_device(s:str)->str:
    d="".join(ch for ch in s.upper() if ch in "0123456789ABCDEF")
    if len(d)!=16: raise ValueError("Device ID должен содержать 16 HEX-символов")
    return d

def generate(device:str, customer:str="", note:str="")->str:
    device=normalize_device(device)
    private=serialization.load_pem_private_key(KEYFILE.read_bytes(),password=None)
    payload={"v":1,"type":"lifetime","device":device}
    payload_b64=b64(json.dumps(payload,separators=(",",":"),sort_keys=True).encode())
    sig=private.sign(payload_b64.encode("ascii"),padding.PKCS1v15(),hashes.SHA256())
    license_code="M6L1."+payload_b64+"."+b64(sig)
    new=not LOGFILE.exists()
    with LOGFILE.open("a",newline="",encoding="utf-8-sig") as f:
        w=csv.writer(f)
        if new:w.writerow(["created_utc","device_id","customer","note","license"])
        w.writerow([datetime.now(timezone.utc).isoformat(),device,customer,note,license_code])
    return license_code

def cli():
    if not KEYFILE.exists():
        print("Нет приватного ключа:",KEYFILE); return 2
    device=input("Device ID из приложения: ").strip()
    customer=input("Покупатель (необязательно): ").strip()
    note=input("Примечание (необязательно): ").strip()
    try:
        code=generate(device,customer,note)
    except Exception as e:
        print("Ошибка:",e); return 1
    print("\nLIFETIME LICENSE:\n"+code)
    print("\nЗаписано в",LOGFILE)
    return 0

if __name__=="__main__":
    raise SystemExit(cli())
