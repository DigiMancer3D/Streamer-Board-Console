"""Rename the display name of an SBC adapter without modifying its stable app ID.

Stores names in SBC/adapters/<app_id>.json, which the existing load_apps()
uses on every launch. No changes to launch paths, hotkeys or process IDs.
"""
from __future__ import annotations
import json
import os
import re
import tempfile
from datetime import datetime
from pathlib import Path
from tkinter import simpledialog, messagebox

VALID_ID=re.compile(r'^[A-Za-z0-9_.-]{1,120}$')

def save_adapter_name(root: Path, app_id: str, new_name: str):
    root=Path(root).resolve()
    app_id=str(app_id)
    name=str(new_name).strip()
    if not VALID_ID.fullmatch(app_id):
        raise ValueError('Invalid adapter ID')
    if not name or len(name)>90 or any(ord(c)<32 for c in name):
        raise ValueError('Name must be 1–90 printable characters')
    adapters=(root/'adapters').resolve()
    path=(adapters/(app_id+'.json')).resolve()
    if path.parent!=adapters or not path.is_file():
        raise FileNotFoundError('Adapter JSON not found: '+str(path))
    raw=path.read_bytes()
    data=json.loads(raw.decode('utf-8'))
    if data.get('app_id')!=app_id:
        raise ValueError('App ID in adapter file does not match selected adapter')
    old_name=data.get('display_name','')
    if old_name==name:return str(old_name),str(name),None
    data['display_name']=name
    stamp=datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    backup=path.with_name(path.name+'.pre-rename.'+stamp+'.bak')
    backup.write_bytes(raw)
    encoded=(json.dumps(data,ensure_ascii=False,indent=2)+'\n').encode('utf-8')
    fd,temp_name=tempfile.mkstemp(prefix='.sbc-name-',dir=adapters)
    try:
        with os.fdopen(fd,'wb') as output:
            output.write(encoded)
            output.flush();os.fsync(output.fileno())
        os.chmod(temp_name,path.stat().st_mode & 0o777)
        os.replace(temp_name,path)
    finally:
        if os.path.exists(temp_name):os.unlink(temp_name)
    return str(old_name),name,backup

def rename_app(console, app, frame):
    name=simpledialog.askstring('Rename SBC app',
         'New display name for '+str(app.display_name)+'\n\n'
         'This changes its SBC label, not its app ID or launcher.',
         parent=console.root,initialvalue=str(app.display_name))
    if name is None:return
    try:
        old,new,backup=save_adapter_name(Path(__file__).resolve().parent,app.app_id,name)
        app.display_name=new
        frame.configure(text=new)
        console.status_var.set(f'App renamed: {old} → {new}')
        console.refresh_all()
    except Exception as exc:
        messagebox.showerror('Rename failed',str(exc),parent=console.root)
