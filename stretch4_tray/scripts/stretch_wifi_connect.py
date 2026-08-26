#!/usr/bin/env python3
"""Connect Stretch to a Wi-Fi network by showing its QR code to the center camera.

Point a phone displaying a standard Wi-Fi QR code (iOS: Settings > Wi-Fi > the
network > Share Password; Android: Settings > Network & internet > the network >
Share) at the robot's center camera. The credentials in the code are handed to
`nmcli`, which joins the network.
"""

import subprocess
import sys
from pathlib import Path

import cv2
from stretch4_body.core.hello_utils import play_sound

MEDIA_DIR = Path(__file__).parent.parent / "media"

SOUNDS = {
    "ready": MEDIA_DIR / "wifi_scan_ready.wav",
    "success": MEDIA_DIR / "wifi_connected.wav",
    "fail": MEDIA_DIR / "wifi_failed.wav",
}

WINDOW_NAME = "Stretch Wi-Fi QR Scanner"

STREAM_TIMEOUT_S = 1.0
"""Give up on a frame after this long so the preview window still handles key presses while the camera is quiet."""


def play_cue(cue):
    """Plays one of the scanner's WAV cues through the robot's speaker."""
    play_sound(str(SOUNDS[cue]))


def parse_wifi_qr(data):
    r"""Parses the standard Wi-Fi QR payload `WIFI:S:<ssid>;T:<auth>;P:<password>;;`.

    Fields may contain `\;`, `\:`, `\,` and `\\` escapes, so the payload is walked one
    character at a time rather than split on `;`. Returns `(ssid, password)`, either of
    which is None when the code does not carry that field.
    """
    if not data.startswith("WIFI:"):
        return None, None

    fields = {}
    key, value, is_escaped = None, "", False
    for character in data[len("WIFI:"):]:
        if is_escaped:
            value += character
            is_escaped = False
        elif character == "\\":
            is_escaped = True
        elif character == ":" and key is None:
            key, value = value, ""
        elif character == ";":
            if key is not None:
                fields[key] = value
            key, value = None, ""
        else:
            value += character

    return fields.get("S") or None, fields.get("P") or None


def find_wifi_qr(detector, image):
    """Returns `(ssid, password, corners)` for the first Wi-Fi QR code in `image`, or `(None, None, None)`."""
    is_found, decoded_codes, all_corners, _ = detector.detectAndDecodeMulti(image)
    if not is_found:
        return None, None, None

    for data, corners in zip(decoded_codes, all_corners):
        ssid, password = parse_wifi_qr(data)
        if ssid:
            return ssid, password, corners

    return None, None, None


def connect_wifi(ssid, password):
    """Joins `ssid` with `nmcli`, playing the success or failure cue. Returns True when connected."""
    print(f"\n[*] Connecting to Wi-Fi network: {ssid}...")

    command = ["nmcli", "device", "wifi", "connect", ssid]
    if password:
        command += ["password", password]

    try:
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        print("[+] Successfully connected!")
        print(result.stdout)
        play_cue("success")
        return True
    except subprocess.CalledProcessError as e:
        print("[-] Connection failed:")
        print(e.stderr)
        play_cue("fail")
        return False


def stream_center_camera():
    """Yields BGR frames from the robot's center camera."""
    try:
        from stretch_python_bridge import stream_camera_center
    except ImportError:
        raise ImportError(
            "stretch_python_bridge not found. Did you colcon build? Please source your ROS 2 workspace."
        )

    for frame in stream_camera_center(timeout=STREAM_TIMEOUT_S):
        yield None if frame is None else frame.image


def scan_for_wifi_qr():
    """Shows the center camera until a Wi-Fi QR code is scanned. Returns `(ssid, password)`, or `(None, None)` if the user quit."""
    detector = cv2.QRCodeDetector()
    is_camera_ready = False

    cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)

    for image in stream_center_camera():
        if image is not None:
            if not is_camera_ready:
                # The camera is live and the scan loop is about to run, so cue the user to hold up the code.
                is_camera_ready = True
                play_cue("ready")
                print(
                    "[*] Center camera active. Hold your phone's Wi-Fi QR code up to the"
                    " camera. Press 'q' to quit."
                )

            ssid, password, corners = find_wifi_qr(detector, image)
            if ssid:
                print(f"[+] Found Wi-Fi QR code for: {ssid}")
                cv2.polylines(image, [corners.astype(int)], True, (0, 255, 0), 3)
                cv2.imshow(WINDOW_NAME, image)
                cv2.waitKey(2000)  # Leave the outlined code on screen for 2 seconds.
                return ssid, password

            cv2.imshow(WINDOW_NAME, image)

        if cv2.getWindowProperty(WINDOW_NAME, cv2.WND_PROP_VISIBLE) < 1:
            break
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    return None, None


def main():
    try:
        ssid, password = scan_for_wifi_qr()
    finally:
        cv2.destroyAllWindows()

    if not ssid:
        print("[*] No Wi-Fi QR code scanned.")
        return 1

    return 0 if connect_wifi(ssid, password) else 1


if __name__ == "__main__":
    sys.exit(main())
