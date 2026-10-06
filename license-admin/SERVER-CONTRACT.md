# Mazda6GH License Server — server contract

Production endpoints expected by the Android client:

POST /activate
{"key":"M6GH-XXXX-XXXX-XXXX","device_id":"<sha256>"}

Success:
{"ok":true,"license":"lifetime","token":"<server-signed-token>"}

Already bound to another device:
{"ok":false,"error":"DEVICE_MISMATCH"}

Unknown/revoked key:
{"ok":false,"error":"INVALID_KEY"}

Admin operations:
- create lifetime key
- list FREE / ACTIVE / REVOKED
- reset device binding
- revoke / restore license

IMPORTANT: admin-panel.html currently generates TEST inventory locally in the owner's browser.
It is intentionally not the authority for production activation. The next deployment step is
to connect both the panel and Android app to a private server/database so secrets never ship in APK.
