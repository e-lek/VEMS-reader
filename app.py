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
    s = serial.Serial('/dev/ttyS1',19200)
    dbsavecount = 0
    filesavecount = 0
    loaddbcount = 0
    cursor = db.cursor()
    
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
                print(ize) 

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

        if int(args.get('dbsavecount') or 0) > dbsavecount :
            if len(dataList)>0:
                print("db save")
                
                fuj = str(dataList).replace("'", "\"")
                
                cursor.execute("SELECT MAX(id) FROM autodata")
                zvonzik = cursor.fetchone()
                if zvonzik[0] is None:
                    dbid=0
                else:
                    dbid=zvonzik[0]
                dbid=dbid + 1
                cursor.execute("INSERT INTO autodata (id, data) VALUES (%s, %s)", (dbid, fuj))
                db.commit()
            
                dbsavecount=dbsavecount+1
                dataList = []
            
        if int(args.get('filesavecount') or 0) > filesavecount :
            if len(dataList)>0:
                print("file save")
                
                fuj = str(dataList).replace("'", "\"")
                
                f = open("text.txt","r")
                txt=f.read()
                f.close()
                f = open("text.txt","a+")
                f.write(txt)
                f.write(fuj+"\n")
                f.close()
  
                filesavecount=filesavecount+1
                dataList = []
                
        if int(args.get('loaddbcount') or 0) > loaddbcount :
            cursor.execute("SELECT data FROM autodata WHERE id=%s", (args.get('loaddbid'),))
            data = cursor.fetchone()
            socketio.emit('LOADEDdata',{'data': data}, namespace='/test')
            loaddbcount = loaddbcount + 1
                     
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

@socketio.on('disconnect', namespace='/test')
def test_disconnect():
    print('Client disconnected', request.sid)
    
@socketio.on('loaddb', namespace='/test')
def loaddb(message):
    session['loaddbcount']= session.get('loaddbcount', 0) + 1
    session['loaddbid']=int(message['value'])

@socketio.on('savedb', namespace='/test')
def savedb():
    session['dbsavecount']= session.get('dbsavecount', 0) + 1

@socketio.on('loadfile', namespace='/test')
def loadfile(message):
    f = open("text.txt","r")
    ize =f.readlines()
    f.close()
    ono = ize[int(message['value'])-1]
    emit('LOADEDdata',{'data': ono})
    
@socketio.on('savefile', namespace='/test')
def savefile():
    session['filesavecount']= session.get('filesavecount', 0) + 1

if __name__ == '__main__':
    socketio.run(app, host="0.0.0.0", port=80, debug=True)
