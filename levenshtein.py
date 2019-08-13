# Copyright 2019 Ericsson AB.
# For a full list of individual contributors, please see the commit history.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import subprocess
import editdistance
import extensions

codec = "utf-8"
errorHandler = "backslashreplace"

def commitDistance(commit):
    diffs = commit.parents[0].diff(commit)
    aggregated_delta = 0

    for diff in diffs:
        if diff.change_type == "A":
            if extensions.extension_supported(diff.b_path):
                aggregated_delta += blob_size(diff.b_blob)

        if diff.change_type == "M" or diff.change_type.startswith("R"):
            if extensions.extension_supported(diff.b_path):
                aggregated_delta += blob_delta(commit.parents[0].__str__() + ":" + diff.a_path, commit.__str__() + ":" + diff.b_path)

        if diff.change_type == "D":
            if extensions.extension_supported(diff.a_path):
                aggregated_delta += blob_size(diff.a_blob)

    return aggregated_delta

def blob_size(blob):
    blob_size = len(blob.data_stream.read().decode(codec, errorHandler))
    return blob_size

def blob_delta(file_a, file_b):
    diff = subprocess.check_output(["git", "--no-pager", "diff", file_a, file_b]).decode(codec, errorHandler)

    aggregatedDistance = 0
    contentA = ""
    contentB = ""
    previous_line_was_plus = False
    for line in diff.split("\n"):
        if line.startswith("---") or line.startswith("+++"):
            continue

        if line.startswith("-"):
            contentA += line[1:]

        if line.startswith("+"):
            contentB += line[1:]
            previous_line_was_plus = True
        elif previous_line_was_plus:
            aggregatedDistance += editdistance.eval(contentA, contentB)
            contentA = ""
            contentB = ""
            previous_line_was_plus = False

    aggregatedDistance += editdistance.eval(contentA, contentB)
    return aggregatedDistance

class GitDiffError(IOError):
    pass
