# Professional Dark Theme / Cyberpunk-ish Style

APP_STYLE = """
QMainWindow {
    background-color: #121212;
    color: #E0E0E0;
}

QWidget {
    font-family: 'Segoe UI', 'Roboto', sans-serif;
    font-size: 14px;
    color: #E0E0E0;
}

/* Group Boxes / Panels */
QFrame#Panel {
    background-color: #1E1E1E;
    border: 1px solid #333;
    border-radius: 8px;
}

QLabel#Header {
    font-size: 18px;
    font-weight: bold;
    color: #00ADB5;
    padding-bottom: 5px;
    border-bottom: 2px solid #00ADB5;
}

QLabel#StatValue {
    font-size: 24px;
    font-weight: bold;
    color: #EEEEEE;
}

QLabel#StatLabel {
    font-size: 12px;
    color: #AAAAAA;
}

/* Buttons */
QPushButton {
    background-color: #2D2D2D;
    border: 1px solid #3E3E3E;
    border-radius: 4px;
    padding: 8px 16px;
    color: #E0E0E0;
    font-weight: 600;
}

QPushButton:hover {
    background-color: #3E3E3E;
    border-color: #00ADB5;
}

QPushButton:pressed {
    background-color: #00ADB5;
    color: #121212;
}

QPushButton#ActionBtn {
    background-color: #00ADB5;
    color: #121212;
    border: none;
}

QPushButton#ActionBtn:hover {
    background-color: #00FFF5;
}

QPushButton#StopBtn {
    background-color: #CF6679;
    color: #121212;
    border: none;
}

QPushButton#StopBtn:hover {
    background-color: #FF8A80;
}

/* Traffic Lights */
QLabel#LightRed {
    background-color: #CF6679;
    color: #121212;
    border-radius: 4px;
    padding: 4px;
    font-weight: bold;
}

QLabel#LightGreen {
    background-color: #03DAC6;
    color: #121212;
    border-radius: 4px;
    padding: 4px;
    font-weight: bold;
}

QLabel#LightYellow {
    background-color: #FBC02D;
    color: #121212;
    border-radius: 4px;
    padding: 4px;
    font-weight: bold;
}
"""
