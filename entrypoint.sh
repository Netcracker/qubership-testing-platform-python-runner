#!/bin/bash
# Copyright 2024-2025 NetCracker Technology Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

set -e
source /app/scripts/trace-init.sh
source /app/scripts/logging.sh

# Main test job entrypoint script - coordinates all modules
log "🔧 Starting test job entrypoint script..."
log "📁 Working directory: $(pwd)"
log "📅 Timestamp: $(date)"

# Set default upload method
export UPLOAD_METHOD="${UPLOAD_METHOD:-sync}"
log "📤 Upload method: $UPLOAD_METHOD"

# Import modular components
source /app/scripts/init.sh
source /app/scripts/git-clone.sh
source /app/scripts/runtime-setup.sh
source /app/scripts/test-runner.sh
source /app/scripts/upload-monitor.sh
source /app/scripts/email-notification/generate-email-notification-json.sh
source /app/scripts/native-report.sh

# Execute main workflow
log "🚀 Starting test execution workflow..."

init_environment
clone_repository
setup_runtime_environment
start_upload_monitoring
run_tests
generate_email_notification_json
save_native_report $TMP_DIR/test-results
finalize_upload

sleep 30

log "✅ Test job finished successfully!"