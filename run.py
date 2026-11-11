"""Local entrypoint: python run.py. No debug server or public binding."""
import os
import sys
import threading
from backend.app import create_app
from backend.models import db
from backend.seed import seed

app = create_app()


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        seed(app.instance_path, app.config['DEMO_MODE'])
    port=int(os.getenv('PORT','5180'))
    print(f'Apex Lab: http://127.0.0.1:{port}', flush=True)
    print('Admin credentials: instance/initial-admin.txt (local only)', flush=True)
    if '--open' in sys.argv:
        def open_when_ready():
            import webbrowser
            import urllib.request
            for _ in range(20):
                try:
                    with urllib.request.urlopen(f'http://127.0.0.1:{port}/api/health',timeout=1) as response:
                        if response.status==200:
                            webbrowser.open(f'http://127.0.0.1:{port}')
                            return
                except Exception:
                    threading.Event().wait(1)
        threading.Thread(target=open_when_ready,daemon=True).start()
    try:
        from waitress import serve
        serve(app,host='127.0.0.1',port=port,threads=4)
    except ImportError:
        app.run(host='127.0.0.1',port=port,debug=False,use_reloader=False)
