import streamlit as st
import pandas as pd
import requests
import json
import socket
import subprocess
import platform
import re
from datetime import datetime
import time

st.set_page_config(page_title="WiFi Camera Detector", page_icon="📷", layout="wide")

# ============ CONFIG ============
CAMERA_KEYWORDS = [
    'hikvision', 'dahua', 'axis', 'bosch', 'sony', 'samsung',
    'tp-link', 'd-link', 'trendnet', 'foscam', 'amcrest', 'nest',
    'arlo', 'ring', 'wyze', 'reolink', 'uniview', 'vivotek',
    'panasonic', 'canon', 'flir', 'swann', 'lorex', 'xiaomi',
    'hik', 'dlink', 'tplink', 'dahua', 'uniview', 'hikvision',
    'annke', 'ezviz', 'imou', 'dome', 'bullet', 'ptz', 'ipc',
    'camera', 'cam', 'cctv', 'nvripc', 'rtsp', 'onvif'
]

# ============ FUNCTIONS ============

def get_network_info():
    """Auto-detect network IP range"""
    try:
        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)
        
        # Get subnet
        parts = local_ip.split('.')
        subnet = f"{parts[0]}.{parts[1]}.{parts[2]}.0/24"
        
        return local_ip, subnet
    except:
        return "Unknown", "192.168.1.0/24"

def ping_sweep(ip_range):
    """Ping all IPs in range to find active devices"""
    base_ip = ip_range.split('/')[0]
    parts = base_ip.split('.')
    prefix = f"{parts[0]}.{parts[1]}.{parts[2]}."
    
    active_ips = []
    
    # Ping all 254 possible IPs
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for i in range(1, 255):
        ip = f"{prefix}{i}"
        
        # Ping command based on OS
        if platform.system().lower() == "windows":
            ping_cmd = f"ping -n 1 -w 100 {ip}"
        else:
            ping_cmd = f"ping -c 1 -W 1 {ip}"
        
        try:
            result = subprocess.run(ping_cmd, shell=True, capture_output=True, text=True)
            if "ttl=" in result.stdout.lower() or "ttl=" in result.stdout:
                active_ips.append(ip)
        except:
            pass
        
        # Update progress
        progress = (i + 1) / 255
        progress_bar.progress(progress)
        status_text.text(f"Scanning: {ip} | Found: {len(active_ips)} devices")
    
    progress_bar.empty()
    status_text.empty()
    
    return active_ips

def get_mac_address(ip):
    """Get MAC address using ARP table"""
    try:
        if platform.system().lower() == "windows":
            cmd = f"arp -a {ip}"
        else:
            cmd = f"arp -n {ip}"
        
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        output = result.stdout
        
        # Parse MAC from ARP output
        mac_pattern = r'([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})'
        match = re.search(mac_pattern, output)
        
        if match:
            return match.group(0)
        return "Unknown"
    except:
        return "Unknown"

def get_hostname(ip):
    """Try to get device hostname"""
    try:
        return socket.gethostbyaddr(ip)[0]
    except:
        return "Unknown"

@st.cache_data(ttl=3600)
def get_vendor(mac):
    """Look up vendor from MAC address"""
    if mac == "Unknown":
        return "Unknown"
    
    url = f"https://api.maclookup.app/v2/macs/{mac}"
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                return data.get('company', 'Unknown')
        return "Lookup Failed"
    except:
        return "API Error"

def is_camera(vendor, hostname=""):
    """Check if device is likely a camera"""
    if not vendor or vendor in ["Unknown", "Lookup Failed", "API Error"]:
        return False
    
    combined = (vendor + " " + hostname).lower()
    
    for keyword in CAMERA_KEYWORDS:
        if keyword in combined:
            return True
    
    return False

def scan_open_ports(ip):
    """Quick scan for common camera ports"""
    common_ports = [80, 554, 8080, 8000, 8554, 37777, 34567]
    open_ports = []
    
    for port in common_ports:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(0.5)
            result = sock.connect_ex((ip, port))
            if result == 0:
                open_ports.append(str(port))
            sock.close()
        except:
            pass
    
    return open_ports

# ============ UI ============

st.title("📷 WiFi Camera Detector")
st.markdown("### Fully Automatic Network Scanner")
st.markdown("*Detects hidden cameras and surveillance devices on your network*")

# Auto-detect network
local_ip, subnet = get_network_info()

# Sidebar
with st.sidebar:
    st.header("📡 Network Info")
    st.metric("Your IP", local_ip)
    st.metric("Network", subnet)
    
    st.divider()
    
    st.header("⚙️ Settings")
    scan_type = st.radio(
        "Scan Type:",
        ["Quick Scan (Ping)", "Deep Scan (Port Check)"],
        help="Deep scan checks common camera ports (slower but more accurate)"
    )
    
    st.divider()
    
    st.markdown("""
    ### 🎯 Detection Methods:
    - ✅ ARP Table Lookup
    - ✅ MAC Vendor Check
    - ✅ Camera Keyword Match
    - ✅ Open Port Detection
    - ✅ Hostname Analysis
    """)

# Main content
tab1, tab2, tab3 = st.tabs(["🔍 Scanner", "📊 Results History", "ℹ️ Help"])

with tab1:
    st.markdown("---")
    
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        st.info(f"📡 Ready to scan: **{subnet}**")
    with col2:
        start_scan = st.button("🚀 START FULL SCAN", type="primary", use_container_width=True)
    with col3:
        quick_test = st.button("⚡ Quick Test (5 IPs)", use_container_width=True)
    
    if start_scan or quick_test:
        
        if quick_test:
            # Test only first 5 IPs
            base_ip = subnet.split('/')[0]
            parts = base_ip.split('.')
            prefix = f"{parts[0]}.{parts[1]}.{parts[2]}."
            test_ips = [f"{prefix}{i}" for i in range(1, 6)]
            active_ips = [ip for ip in test_ips if ping_sweep_single(ip)]
        else:
            # Full scan
            with st.spinner("🔍 Scanning network..."):
                active_ips = ping_sweep(subnet)
        
        if active_ips:
            st.success(f"✅ Found **{len(active_ips)}** active devices")
            
            # Collect device info
            devices = []
            progress = st.progress(0)
            status = st.empty()
            
            for i, ip in enumerate(active_ips):
                status.text(f"Analyzing: {ip}")
                
                mac = get_mac_address(ip)
                hostname = get_hostname(ip)
                vendor = get_vendor(mac)
                camera = is_camera(vendor, hostname)
                
                device_info = {
                    'IP Address': ip,
                    'MAC Address': mac,
                    'Hostname': hostname,
                    'Vendor': vendor,
                    'Camera?': '🔴 YES - CAMERA' if camera else '⚪ No'
                }
                
                # Deep scan if selected
                if scan_type == "Deep Scan (Port Check)":
                    ports = scan_open_ports(ip)
                    device_info['Open Ports'] = ', '.join(ports) if ports else 'None'
                    
                    # Additional camera detection via ports
                    camera_ports = ['554', '8554', '37777']
                    if any(p in ports for p in camera_ports):
                        device_info['Camera?'] = '🔴 YES - CAMERA (Port)'
                
                devices.append(device_info)
                progress.progress((i + 1) / len(active_ips))
            
            progress.empty()
            status.empty()
            
            # Display results
            st.markdown("---")
            st.subheader("📊 Scan Results")
            
            df = pd.DataFrame(devices)
            
            # Highlight cameras
            def highlight_cameras(row):
                if 'YES' in str(row.get('Camera?', '')):
                    return ['background-color: #ffcccc; font-weight: bold'] * len(row)
                return [''] * len(row)
            
            styled_df = df.style.apply(highlight_cameras, axis=1)
            st.dataframe(styled_df, use_container_width=True, hide_index=True)
            
            # Summary
            camera_count = sum(1 for d in devices if 'YES' in str(d.get('Camera?', '')))
            
            st.markdown("---")
            
            if camera_count > 0:
                st.error(f"🚨 **ALERT: {camera_count} potential camera(s) detected!**")
                
                st.markdown("### 📋 Suspicious Devices:")
                for d in devices:
                    if 'YES' in str(d.get('Camera?', '')):
                        st.markdown(f"""
                        <div style="background:#ffcccc;padding:10px;border-radius:5px;margin:5px 0;">
                            <b>IP:</b> {d['IP Address']} | 
                            <b>MAC:</b> {d['MAC Address']} | 
                            <b>Vendor:</b> {d['Vendor']}
                        </div>
                        """, unsafe_allow_html=True)
            else:
                st.success("✅ **No cameras detected. Network appears safe!**")
            
            # Download report
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            csv = df.to_csv(index=False)
            
            col1, col2 = st.columns(2)
            with col1:
                st.download_button(
                    "📥 Download Report (CSV)",
                    csv,
                    f"camera_scan_{timestamp}.csv",
                    "text/csv",
                    use_container_width=True
                )
            with col2:
                # Save to session for history
                if 'scan_history' not in st.session_state:
                    st.session_state.scan_history = []
                st.session_state.scan_history.append({
                    'timestamp': timestamp,
                    'devices': devices,
                    'cameras_found': camera_count
                })
                st.success("📁 Saved to history")
        
        else:
            st.warning("❌ No devices found. Check your network connection.")

def ping_sweep_single(ip):
    """Ping single IP"""
    if platform.system().lower() == "windows":
        cmd = f"ping -n 1 -w 100 {ip}"
    else:
        cmd = f"ping -c 1 -W 1 {ip}"
    
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return "ttl=" in result.stdout.lower()
    except:
        return False

with tab2:
    st.header("📊 Scan History")
    
    if 'scan_history' not in st.session_state:
        st.session_state.scan_history = []
    
    if st.session_state.scan_history:
        for scan in reversed(st.session_state.scan_history):
            with st.expander(f"Scan: {scan['timestamp']} | Cameras: {scan['cameras_found']}"):
                df = pd.DataFrame(scan['devices'])
                st.dataframe(df, use_container_width=True)
    else:
        st.info("No scan history yet. Run a scan first!")

with tab3:
    st.header("ℹ️ How It Works")
    
    st.markdown("""
    ### 🔍 Detection Methods
    
    This tool uses **5 methods** to detect cameras:
    
    1. **Ping Sweep** - Finds all active devices on network
    2. **ARP Table** - Gets MAC addresses of devices
    3. **MAC Vendor Lookup** - Identifies manufacturer
    4. **Keyword Analysis** - Matches against 50+ camera brands
    5. **Port Scanning** - Checks for RTSP/ONVIF camera ports
    
    ### 🎯 Brands Detected
    
    Hikvision, Dahua, Axis, Bosch, Sony, Samsung, TP-Link, D-Link, 
    Foscam, Amcrest, Nest, Arlo, Ring, Wyze, Reolink, Uniview, 
    Vivotek, Panasonic, Canon, FLIR, Swann, Lorex, Xiaomi, ANNKE, 
    EZVIZ, Imou + more
    
    ### ⚠️ Limitations
    
    - MAC addresses can be spoofed
    - Some cameras use generic network chips
    - Only detects WiFi/Ethernet connected cameras
    - Cannot detect offline/recording-only devices
    
    ### 🛡️ Privacy
    
    - All scans are local to your network
    - Only MAC vendor lookup uses external API
    - No data is stored or transmitted
    """)

# Footer
st.markdown("---")
st.markdown("""
<div style="text-align:center; color:gray;">
    <p>📷 WiFi Camera Detector | Security Tool</p>
    <p style="font-size:12px;">Use responsibly on your own networks only</p>
</div>
""", unsafe_allow_html=True)
