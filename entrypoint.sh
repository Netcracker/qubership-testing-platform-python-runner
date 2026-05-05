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

# Main test job entrypoint script - coordinates all modules
echo "🔧 Starting test job entrypoint script..."
echo "📁 Working directory: $(pwd)"
echo "📅 Timestamp: $(date)"

# Set default upload method
export UPLOAD_METHOD="${UPLOAD_METHOD:-sync}"
echo "📤 Upload method: $UPLOAD_METHOD"

# Import modular components
# shellcheck disable=SC1091
source /scripts/error-handler.sh
# shellcheck disable=SC1091
source /scripts/init.sh
# shellcheck disable=SC1091
source /scripts/git-clone.sh
# shellcheck disable=SC1091
source /scripts/runtime-setup.sh
# shellcheck disable=SC1091
source /scripts/test-runner.sh
# shellcheck disable=SC1091
source /scripts/upload-monitor.sh
# shellcheck disable=SC1091
source /scripts/email-notification/generate-email-notification-json.sh
# shellcheck disable=SC1091
source /scripts/native-report.sh
# shellcheck disable=SC1091
source /scripts/envgene.sh
# shellcheck disable=SC1091
source /scripts/render-environment-configuration.sh

# Execute main workflow
echo "🚀 Starting test execution workflow..."

# finalize_once() is defined in error-handler.sh (sourced above).
# Register it here after all scripts are sourced so every function it calls is available.
trap 'finalize_once' EXIT

init_environment              || fail "Environment initialization failed"
clone_repository              || fail "Repository clone failed"
render_environment_configuration || fail "Render Environment Configuration Failed"
load_envgene                  || fail "Load Envgen Failed"
setup_runtime_environment     || fail "Runtime setup failed"
start_upload_monitoring
run_tests                     || fail "Test runner failed"

echo "✅ Test job finished successfully!"