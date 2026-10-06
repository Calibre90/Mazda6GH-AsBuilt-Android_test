# License server
Set environment variables `ADMIN_PASSWORD` and `ADMIN_SESSION_SECRET`, then run:
`pip install -r license_server/requirements.txt && python license_server/app.py`

Admin: /admin
Activation API: POST /api/activate with JSON {"key":"M6GH-...","device":"..."}.

For production use persistent storage/volume for licenses.db and HTTPS. Do not put ADMIN_PASSWORD in the APK.
