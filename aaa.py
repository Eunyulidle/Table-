import cv2
import torch
import time
from PIL import Image, ImageTk
import tkinter as tk
from tkinter import messagebox
import subprocess, urllib.request, os

# 환경 설정 함수들 (생략, 위와 동일)
def setup():
    def is_git_installed():
        try:
            subprocess.check_output(['git', '--version'])
            return True
        except Exception:
            return False

    def download_yolov5s_pt():
        if not os.path.exists("yolov5s.pt"):
            print("[🔽] yolov5s.pt 모델 다운로드 중...")
            url = "https://github.com/ultralytics/yolov5/releases/download/v6.0/yolov5s.pt"
            urllib.request.urlretrieve(url, "yolov5s.pt")

    def clone_yolov5_repo():
        if not os.path.exists("yolov5"):
            os.system("git clone https://github.com/ultralytics/yolov5.git")

    def install_requirements():
        try:
            import cv2, torch, PIL, tkinter
        except:
            os.system("pip install -r yolov5/requirements.txt")
            os.system("pip install opencv-python pillow tkinter torchvision pandas pyyaml")

    if is_git_installed():
        clone_yolov5_repo()
    download_yolov5s_pt()
    install_requirements()

def load_model():
    return torch.hub.load('yolov5', 'custom', path='yolov5s.pt', source='local', force_reload=True)

setup()
model = load_model()

cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_FPS, 60)

window = tk.Tk()
window.title("YOLOv5 사분면 동시 시간 추적")
window.geometry("900x500")
window.resizable(False, False)

canvas = tk.Canvas(window, width=640, height=480)
canvas.pack(side=tk.LEFT)

control_frame = tk.Frame(window)
control_frame.pack(side=tk.RIGHT, padx=10)

fps_label = tk.Label(control_frame, text="", font=("맑은 고딕", 15))
fps_label.pack(pady=(10, 20))

time_label = tk.Label(control_frame, text="", font=("맑은 고딕", 12), justify="left")
time_label.pack(pady=(0, 20))

reversal = -1
boxing = 1
texting = 1
accuracy = -1
stoping = -1

# 각 사분면에 사람이 있는지 현재 상태
quadrant_presence = {
    'top_left': False,
    'top_right': False,
    'bottom_left': False,
    'bottom_right': False
}

# 각 사분면별 누적 시간(초)
quadrant_times = {
    'top_left': 0,
    'top_right': 0,
    'bottom_left': 0,
    'bottom_right': 0
}

# 마지막 업데이트 시간
last_update_time = time.time()

def toggle(var_name, button, texts):
    globals()[var_name] *= -1
    button.config(text=texts[0] if globals()[var_name] == 1 else texts[1])

def turn_stop():
    global stoping
    stoping *= -1

btns = [
    ("reversal", "좌우반전", ["좌우반전", "원래대로"]),
    ("boxing", "테두리 숨김", ["테두리 숨김", "테두리 표시"]),
    ("texting", "텍스트 숨김", ["텍스트 숨김", "텍스트 표시"]),
    ("accuracy", "정확도 숨김", ["정확도 숨김", "정확도 표시"])
]

for var, text, alt in btns:
    tk.Button(control_frame, text=text, width=15,
              command=lambda v=var, t=text, a=alt: toggle(v, btn_map[v], a)
              ).pack(pady=5)

btn_map = {var: control_frame.winfo_children()[i] for i, (var, *_rest) in enumerate(btns)}

tk.Button(control_frame, text="전체 숨김", command=lambda: [toggle("boxing", btn_map["boxing"], btns[1][2]),
                                                            toggle("texting", btn_map["texting"], btns[2][2]),
                                                            toggle("accuracy", btn_map["accuracy"], btns[3][2])]).pack(pady=5)

stop_btn = tk.Button(control_frame, text="⏸️", font=('맑은 고딕', 25), command=turn_stop)
stop_btn.pack(pady=5)

def update_frame():
    global stoping, quadrant_presence, quadrant_times, last_update_time

    if stoping == 1:
        stop_btn.config(text="▶️")
        messagebox.showinfo("일시정지", "재시작하려면 다시 누르세요.")
        stop_btn.config(text="⏸️")
        stoping *= -1

    start_time = time.time()

    ret, frame = cap.read()
    if not ret:
        messagebox.showerror("오류", "웹캠을 사용할 수 없습니다.")
        window.destroy()
        return

    if reversal == 1:
        frame = cv2.flip(frame, 1)

    image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    results = model(image)
    bboxes = results.xyxy[0].numpy()

    # 현재 프레임에서 각 사분면별 사람 감지 상태 임시 기록
    current_presence = {
        'top_left': False,
        'top_right': False,
        'bottom_left': False,
        'bottom_right': False
    }

    h, w = frame.shape[:2]

    for box in bboxes:
        if model.names[int(box[5])] != 'person':
            continue

        x1, y1, x2, y2 = box[:4].astype(int)
        conf = box[4]
        cx, cy = (x1 + x2) // 2, (y1 + y2) // 2

        # 사분면 판단
        if cx < w // 2 and cy < h // 2:
            current_presence['top_left'] = True
        elif cx >= w // 2 and cy < h // 2:
            current_presence['top_right'] = True
        elif cx < w // 2 and cy >= h // 2:
            current_presence['bottom_left'] = True
        else:
            current_presence['bottom_right'] = True

        color = (0, 0, 255)
        if boxing == 1:
            cv2.circle(frame, (cx, cy), 10, color, -1)

        if texting == 1:
            label = f"person" if accuracy == -1 else f"person: {conf:.2f}"
            cv2.putText(frame, label, (x1, y1 - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)

    # 시간 누적
    now = time.time()
    elapsed = now - last_update_time

    for quadrant in quadrant_times.keys():
        if quadrant_presence[quadrant]:
            quadrant_times[quadrant] += elapsed

    # 현재 프레임 기준으로 사분면별 상태 업데이트
    quadrant_presence = current_presence

    last_update_time = now

    # 사분면 선 그리기
    cv2.line(frame, (w//2, 0), (w//2, h), (0, 255, 0), 2)
    cv2.line(frame, (0, h//2), (w, h//2), (0, 255, 0), 2)

    # FPS 계산
    fps = int(1 / (elapsed)) if elapsed > 0 else 0
    fps_label.config(text=f"FPS: {fps}")

    # 사분면별 누적 시간 텍스트
    text = (
        f"LU: {int(quadrant_times['top_left'])}s\n"
        f"RU: {int(quadrant_times['top_right'])}s\n"
        f"LD: {int(quadrant_times['bottom_left'])}s\n"
        f"RD: {int(quadrant_times['bottom_right'])}s"
    )
    time_label.config(text=text)

    # 이미지 렌더링
    img = ImageTk.PhotoImage(image=Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)))
    canvas.create_image(0, 0, anchor=tk.NW, image=img)
    canvas.img = img

    window.after(1, update_frame)

update_frame()
window.mainloop()
cap.release()
cv2.destroyAllWindows()
