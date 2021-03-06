from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit, disconnect
import base64
import numpy as np
import cv2
from flask_httpauth import HTTPDigestAuth
import os
from dotenv import load_dotenv
from engineio.payload import Payload
from queue import Queue, Empty
from custom_flask import CustomFlask

Payload.max_decode_packets = 500
load_dotenv(verbose=True)

image_queue = Queue(maxsize=50)
processed_queue = Queue(maxsize=50)

face_cascade = cv2.CascadeClassifier('haarcascade_frontalface_default.xml')
auth = HTTPDigestAuth()


def _detect_face(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    faces = face_cascade.detectMultiScale(gray, 1.1, 4)
    for (x, y, w, h) in faces:
        cv2.rectangle(img, (x, y), (x + w, y + h), (0, 0, 255), 2)
    return img


def _base64_decode(img):
    _, buffer = cv2.imencode(".jpg", img)
    base64_data = base64.b64encode(buffer)
    base64_data = "data:image/jpg;base64," + base64_data.decode('utf-8')
    return base64_data


def _base64_encode(img_base64):
    img_binary = base64.b64decode(img_base64)
    jpg = np.frombuffer(img_binary, dtype=np.uint8)
    img = cv2.imdecode(jpg, cv2.IMREAD_COLOR)
    return img


def _validate_access_token():
    access_token = request.headers.environ.get('HTTP_X_ACCESS_TOKEN')
    if access_token != os.environ.get("ACCESS_TOKEN"):
        disconnect()


def loop_emit():
    print("start loop")
    while True:
        try:
            img = image_queue.get()
        except Empty:
            continue

        processed_img = _detect_face(img)
        base64_data = _base64_decode(processed_img)
        processed_queue.put(base64_data)


app = CustomFlask(__name__, background_task=loop_emit)
app.config['SECRET_KEY'] = os.environ.get("APP_SECRET")
socketio = SocketIO(app, cors_allowed_origins="*")


@auth.get_password
def get_pw(username):
    if username == os.environ.get("USER_NAME"):
        return os.environ.get("PASSWORD")
    return None


@app.route('/health_check')
def health_check():
    return "Status OK"


@app.route('/sender')
@auth.login_required
def sender():
    return render_template("sender.html", access_token=os.environ.get("ACCESS_TOKEN"))


@app.route('/receiver')
@auth.login_required
def receiver():
    return render_template("receiver.html", access_token=os.environ.get("ACCESS_TOKEN"))


@socketio.on('connect', namespace="/image")
def test_connect():
    _validate_access_token()

    referer = request.referrer

    if referer is None or 'receiver' not in referer:
        image_queue.queue.clear()
        processed_queue.queue.clear()


@socketio.on("send image", namespace="/image")
def parse_image(json):
    _validate_access_token()

    img_base64 = json["data"].split(',')[1]
    img = _base64_encode(img_base64)
    image_queue.put(img)

    try:
        base64_data = processed_queue.get()
    except Empty:
        return
    else:
        emit('return img', base64_data, broadcast=True)


if __name__ == '__main__':
    socketio.run(app, debug=False)