from threading import Lock
from flask import Flask, render_template, session, request, jsonify, url_for
from flask_socketio import SocketIO, emit, disconnect    
import time
import math
import configparser as ConfigParser
import MySQLdb
import json
import serial
import re

async_mode = None

app = Flask(__name__)

config = ConfigParser.ConfigParser()
config.read('config.cfg')
myhost = config.get('mysqlDB', 'host')
myuser = config.get('mysqlDB', 'user')
mypasswd = config.get('mysqlDB', 'passwd')
mydb = config.get('mysqlDB', 'db')

app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app, async_mode=async_mode)
thread = None
thread_lock = Lock()

def background_thread(args):
    count = 0    
    dataList = []
    db = MySQLdb.connect(host=myhost,user=myuser,passwd=mypasswd,db=mydb)
    s = serial.Serial('/dev/ttyACM0',19200)
    
    rpm = 0
    m = 0
    l = 0
    
    while True:

        print(args)
        
        if args.get('btn_value')=='start':

            for i in range(0,2):
                ize = s.readline()
                ize = ize.decode('ascii')
                ono = re.findall(r'([0-9A-F]+)',ize)

                if ono[0]=='1' :
                    rpm = int(ono[2],16)*256 + int(ono[3],16)
            
                if ono[0]=='45' :
                    m = int(ono[2],16)*256 + int(ono[3],16)

                if ono[0]=='69' :
                    l = int(ono[2],16)*256 + int(ono[3],16)
                    l = l/1000
                
            dataDict = {
            "rpm": rpm,
            "map": m,
            "lambda": l }
            
            socketio.emit('AKTUALdata',dataDict, namespace='/test')
            
            dataList.append(dataDict)
            
        else:
            if len(dataList)>0:
                fuj = str(dataList).replace("'", "\"")
                cursor = db.cursor()
                cursor.execute("SELECT MAX(id) FROM graph")
                maxid = cursor.fetchone()
                if maxid[0] is None:
                    maxID=0
                else:
                    maxID=maxid[0]
                newid=maxID + 1
                cursor.execute("INSERT INTO graph (id, hodnoty) VALUES (%s, %s)", (newid, fuj))
                db.commit()
                dataList = []
                count = 0
                
        time.sleep(0.1)

@app.route('/')
def index():
    return render_template('index.html', async_mode=socketio.async_mode)
  
@socketio.on('my_event', namespace='/test')
def test_message(message):   
    session['receive_count'] = session.get('receive_count', 0) + 1 
 
@socketio.on('disconnect_request', namespace='/test')
def disconnect_request():
    session['receive_count'] = session.get('receive_count', 0) + 1
    emit('disconn',{'data': 'Disconnected!'})
    disconnect()

@socketio.on('connect', namespace='/test')
def test_connect():
    global thread
    with thread_lock:
        if thread is None:
            session['btn_value']='stop'
            thread = socketio.start_background_task(target=background_thread, args=session._get_current_object())
    emit('my_response', {'data': 'Connected', 'count': 0})

@socketio.on('click_event', namespace='/test')
def db_message(message):
    print("Start")
    session['btn_value'] = message['value']
    emit('status', {'data': message['value']})

@socketio.on('disconnect', namespace='/test')
def test_disconnect():
    print('Client disconnected', request.sid)

if __name__ == '__main__':
    socketio.run(app, host="0.0.0.0", port=80, debug=True)
