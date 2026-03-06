import sys
import time
from src.core.esp32_bridge import ESP32Bridge

def print_menu():
    print("\n" + "="*40)
    print("  HARDWARE TRAFFIC LIGHT TESTER CLI  ")
    print("="*40)
    print("Commands:")
    print("  1 - Set ALL RED         [R, R, R, R]")
    print("  2 - Set ALL GREEN       [G, G, G, G]")
    print("  3 - Set ALL YELLOW      [Y, Y, Y, Y]")
    print("  4 - Lane 1 GREEN        [G, R, R, R]")
    print("  5 - Lane 2 GREEN        [R, G, R, R]")
    print("  6 - Lane 3 GREEN        [R, R, G, R]")
    print("  7 - Lane 4 GREEN        [R, R, R, G]")
    print("  p - Send PING")
    print("  q - Quit")
    print("="*40)

def main():
    ports = ESP32Bridge.list_ports()
    if not ports:
        print("No COM ports found. Is the ESP32 plugged in?")
        return
        
    print("\nAvailable COM Ports:")
    for idx, p in enumerate(ports):
        print(f"  [{idx}] {p['port']} - {p['desc']}")
        
    port_idx = input("\nEnter the number of the ESP32 port (e.g., 0): ").strip()
    try:
        selected_port = ports[int(port_idx)]['port']
    except (ValueError, IndexError):
        print("Invalid selection. Exiting.")
        return
        
    print(f"\nConnecting to {selected_port}...")
    bridge = ESP32Bridge(port=selected_port, baud=115200, enabled=True)
    if not bridge.connect():
        print("Failed to connect.")
        return
        
    print("Connected successfully!")
    
    while True:
        print_menu()
        cmd = input("Enter command: ").strip().lower()
        
        if cmd == 'q':
            break
        elif cmd == 'p':
            print("Sending PING...")
            if bridge.ping():
                print(">> PONG received! Link is OK.")
            else:
                print(">> No valid PONG response.")
        elif cmd == '1':
            bridge.send_states(['R', 'R', 'R', 'R'])
            print(">> Sent: ALL RED")
        elif cmd == '2':
            bridge.send_states(['G', 'G', 'G', 'G'])
            print(">> Sent: ALL GREEN")
        elif cmd == '3':
            bridge.send_states(['Y', 'Y', 'Y', 'Y'])
            print(">> Sent: ALL YELLOW")
        elif cmd == '4':
            bridge.send_states(['G', 'R', 'R', 'R'])
            print(">> Sent: Lane 1 GREEN")
        elif cmd == '5':
            bridge.send_states(['R', 'G', 'R', 'R'])
            print(">> Sent: Lane 2 GREEN")
        elif cmd == '6':
            bridge.send_states(['R', 'R', 'G', 'R'])
            print(">> Sent: Lane 3 GREEN")
        elif cmd == '7':
            bridge.send_states(['R', 'R', 'R', 'G'])
            print(">> Sent: Lane 4 GREEN")
        else:
            print("Invalid command.")
            
        time.sleep(0.5)
        
    bridge.disconnect()
    print("Disconnected. Goodbye!")

if __name__ == "__main__":
    main()
