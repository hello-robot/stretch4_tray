import os
import re
import subprocess
import cv2
import depthai as dai
from pyzbar.pyzbar import decode


def play_ubuntu_sound(sound_type):
  """Plays native Ubuntu .oga system sounds using built-in desktop utilities."""
  sound_map = {
      "launch": (
          "/usr/share/sounds/freedesktop/stereo/message-new-instant.oga"
      ),
      "success": "/usr/share/sounds/freedesktop/stereo/complete.oga",
      "fail": "/usr/share/sounds/freedesktop/stereo/dialog-error.oga",
  }

  sound_file = sound_map.get(sound_type)

  try:
    if sound_file and os.path.exists(sound_file):
      if os.system("which canberra-gtk-play > /dev/null 2>&1") == 0:
        subprocess.Popen(["canberra-gtk-play", "-f", sound_file])
      elif os.system("which ffplay > /dev/null 2>&1") == 0:
        subprocess.Popen(
            ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", sound_file]
        )
      elif os.system("which mpv > /dev/null 2>&1") == 0:
        subprocess.Popen(["mpv", "--no-video", "--really-quiet", sound_file])
      else:
        print("\a", end="", flush=True)
    else:
      print("\a", end="", flush=True)
  except Exception:
    print("\a", end="", flush=True)


def parse_wifi_qr(data):
  """Parses iPhone Wi-Fi QR string format: WIFI:S:<SSID>;T:<type>;P:<password>;;"""
  if not data.startswith("WIFI:"):
    return None, None

  ssid_match = re.search(r"S:([^;]+);", data)
  pass_match = re.search(r"P:([^;]+);", data)

  ssid = ssid_match.group(1) if ssid_match else None
  password = pass_match.group(1) if pass_match else None

  return ssid, password


def connect_wifi(ssid, password):
  print(f"\n[*] Connecting to Wi-Fi network: {ssid}...")
  try:
    cmd = ["nmcli", "device", "wifi", "connect", ssid, "password", password]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    print("[+] Successfully connected!")
    print(result.stdout)
    play_ubuntu_sound("success")
    return True
  except subprocess.CalledProcessError as e:
    print("[-] Connection failed:")
    print(e.stderr)
    play_ubuntu_sound("fail")
    return False


def main():
  # Create pipeline using modern DepthAI v3 context/syntax
  with dai.Pipeline() as pipeline:
    # Define source camera using the v3 Camera node
    cam = pipeline.create(dai.node.Camera).build()

    # Request an output frame stream (BGR format for OpenCV)
    video_output = cam.requestOutput(
        (1280, 720), type=dai.ImgFrame.Type.BGR888p
    )
    video_queue = video_output.createOutputQueue()

    pipeline.build()
    pipeline.start()

    print(
        "[*] Luxonis OAK camera active. Point your camera at the iPhone Wi-Fi"
        " QR code. Press 'q' to quit."
    )

    # Play launch chime right now—camera is ready and scanning loop is about to start
    play_ubuntu_sound("launch")

    while pipeline.isRunning():
      in_video = video_queue.tryGet()
      if in_video is None:
        continue

      frame = in_video.getCvFrame()

      # Scan for QR codes in the current frame
      for barcode in decode(frame):
        qr_data = barcode.data.decode("utf-8")
        ssid, password = parse_wifi_qr(qr_data)

        if ssid and password:
          print(f"[+] Found Wi-Fi QR Code for: {ssid}")
          pts = barcode.polygon
          if len(pts) == 4:
            pts_array = [(pt.x, pt.y) for pt in pts]
            for j in range(4):
              cv2.line(
                  frame, pts_array[j], pts_array[(j + 1) % 4], (0, 255, 0), 3
              )

          cv2.imshow("Luxonis Wi-Fi QR Scanner", frame)
          cv2.waitKey(2000)  # Pause for 2 seconds
          cv2.destroyAllWindows()

          # Trigger connection
          connect_wifi(ssid, password)
          return

      cv2.imshow("Luxonis Wi-Fi QR Scanner", frame)

      if cv2.waitKey(1) & 0xFF == ord("q"):
        break

  cv2.destroyAllWindows()


if __name__ == "__main__":
  main()