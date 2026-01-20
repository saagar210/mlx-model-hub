#!/bin/bash
# Setup launchd jobs for KAS maintenance and health checks
# Run: ./scripts/setup_launchd.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"

echo "Setting up KAS launchd jobs..."

# Create LaunchAgents directory if needed
mkdir -p "$LAUNCH_AGENTS_DIR"

# Copy plist files
for plist in "$SCRIPT_DIR"/com.kas.*.plist; do
    if [ -f "$plist" ]; then
        filename=$(basename "$plist")
        echo "Installing $filename..."

        # Unload if already loaded
        launchctl unload "$LAUNCH_AGENTS_DIR/$filename" 2>/dev/null || true

        # Copy plist
        cp "$plist" "$LAUNCH_AGENTS_DIR/"

        # Load the job
        launchctl load "$LAUNCH_AGENTS_DIR/$filename"

        echo "  Loaded: $filename"
    fi
done

echo ""
echo "Installed launchd jobs:"
launchctl list | grep com.kas || echo "  (none running yet - scheduled jobs will start at their configured times)"

echo ""
echo "View logs:"
echo "  tail -f /tmp/kas-maintenance.log"
echo "  tail -f /tmp/kas-api.log"

echo ""
echo "To manually trigger maintenance:"
echo "  launchctl start com.kas.maintenance"

echo ""
echo "To unload all KAS jobs:"
echo "  for job in \$(launchctl list | grep com.kas | awk '{print \$3}'); do launchctl unload ~/Library/LaunchAgents/\$job.plist; done"
