#!/usr/bin/env python3
"""
Installation script for Telegram Bot dependencies
Run this before starting the bot to ensure all dependencies are installed
"""

import subprocess
import sys
import os

# Required packages for the Telegram Bot
REQUIRED_PACKAGES = [
    "python-telegram-bot==20.8",
    "flask==3.1.1",
    "flask-cors==6.0.1"
]

def install_package(package):
    """Install a single package using pip"""
    try:
        print(f"Installing {package}...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", package])
        print(f"✅ Successfully installed {package}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install {package}: {e}")
        return False

def check_package_installed(package_name):
    """Check if a package is already installed"""
    try:
        import importlib
        importlib.import_module(package_name.replace('-', '_'))
        return True
    except ImportError:
        return False

def main():
    """Main installation function"""
    print("🔧 Installing Telegram Bot dependencies...")
    print("=" * 50)
    
    failed_packages = []
    
    for package in REQUIRED_PACKAGES:
        package_name = package.split("==")[0]
        
        # Check if already installed
        if check_package_installed(package_name):
            print(f"✅ {package_name} is already installed")
            continue
            
        # Install the package
        if not install_package(package):
            failed_packages.append(package)
    
    print("=" * 50)
    
    if failed_packages:
        print(f"❌ Failed to install: {', '.join(failed_packages)}")
        print("Please install these packages manually:")
        for package in failed_packages:
            print(f"  pip install {package}")
        return False
    else:
        print("✅ All dependencies installed successfully!")
        print("You can now run the bot with: python main.py")
        return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)