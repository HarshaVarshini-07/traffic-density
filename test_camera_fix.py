import cv2
try:
    fourcc = cv2.VideoWriter_fourcc(*"MJPG")
    print(f"VideoWriter_fourcc exists: {fourcc}")
    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FOURCC, fourcc)
    print("Camera property set successfully.")
    cap.release()
except AttributeError:
    print("AttributeError: cv2.VideoWriter_fourcc does not exist.")
except Exception as e:
    print(f"Error: {e}")
