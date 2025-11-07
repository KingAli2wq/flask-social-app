#!/usr/bin/env python3
"""
Workspace cleanup utility - automatically removes temporary test files
"""

import os
from pathlib import Path

def cleanup_workspace():
    """Remove temporary test files, keep essential ones"""
    
    base_dir = Path(__file__).parent
    
    # Essential test files to KEEP
    essential_files = {
        "test_performance.py",
        "test_gui.py", 
        "test_realtime.py",
        "test_startup.py",
        "debug_app.py"
    }
    
    # Patterns for files to DELETE
    cleanup_patterns = [
        "*test_asset*",
        "*test_branding*", 
        "*test_logo*",
        "*test_devecho*",
        "*asset_restoration*",
        "*branding*",
        "*create_logo*",
        "*cleanup_data*"
    ]
    
    print("🧹 DevEcho Workspace Cleanup")
    print("=" * 40)
    
    removed_count = 0
    
    # Remove temporary test files
    for pattern in cleanup_patterns:
        for file_path in base_dir.glob(pattern):
            if file_path.is_file() and file_path.name not in essential_files:
                try:
                    file_path.unlink()
                    print(f"🗑️ Removed: {file_path.name}")
                    removed_count += 1
                except Exception as e:
                    print(f"❌ Failed to remove {file_path.name}: {e}")
    
    # Show essential files that were preserved
    print(f"\n✅ Kept essential files:")
    for essential in essential_files:
        if (base_dir / essential).exists():
            print(f"   📄 {essential}")
    
    print(f"\n📊 Summary:")
    print(f"   🗑️ Removed: {removed_count} temporary files")
    print(f"   📄 Kept: {len(essential_files)} essential test files")
    print(f"   📖 Documentation: DEVECHO_DEVELOPMENT.md")
    
    return removed_count

if __name__ == "__main__":
    cleanup_workspace()