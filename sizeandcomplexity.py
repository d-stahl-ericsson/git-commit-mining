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

from BlobStats import BlobStats
import git
import lizard
import extensions

codec = "utf-8"
errorHandler = "backslashreplace"

def all_blobs_in_tree(tree):
    blobs = {}

    for blob in tree.blobs:
        if extensions.extension_supported(blob.path):
            blobs[blob.path] = blob

    for subtree in tree.trees:
        blobs.update(all_blobs_in_tree(subtree))

    return blobs

def all_blobs_modified_by_commit(commit):
    blobs = {}
    for diff in commit.parents[0].diff(commit):
        if diff.b_blob and extensions.extension_supported(diff.b_blob.path):
            blobs[diff.b_blob.path] = diff.b_blob

    return blobs

def analyze_tree(tree):
    blobs = {}

    for blob in tree.blobs:
        if extensions.extension_supported(blob.path):
            blobs[blob.path] = blob_stats(blob)

    for subtree in tree.trees:
        blobs.update(analyze_tree(subtree))

    return blobs

def blob_stats(blob):
    bs = BlobStats()
    content = blob.data_stream.read().decode(codec, errorHandler)
    f = lizard.analyze_file.analyze_source_code(blob.name, content)
    for function in f.function_list:
        bs.loc += function.nloc
        bs.cyclomaticComplexity += function.cyclomatic_complexity
        bs.functions += 1

    return bs

def tree_delta(commitB):
    commitA = commitB.parents[0]
    diffs = None
    tree_delta = {}

    if commitA:
        diffs = commitA.diff(commitB)
    else:
        diffs = commitB.diff(git.NULL_TREE)

    for diff in diffs:
        if diff.change_type == "A" or diff.change_type == "M":
            if extensions.extension_supported(diff.b_path):
                tree_delta[diff.b_path] = blob_stats(diff.b_blob)

        if diff.change_type == "D":
            if extensions.extension_supported(diff.a_path):
                tree_delta[diff.a_path] = None
        if diff.change_type.startswith("R"):
            if extensions.extension_supported(diff.a_path):
                tree_delta[diff.a_path] = None
            if extensions.extension_supported(diff.b_path):
                tree_delta[diff.b_path] = blob_stats(diff.b_blob)

    return tree_delta

def aggregate_delta(previous_tree, delta_tree):
    delta_loc = 0
    delta_cyclomatic_complexity = 0
    delta_functions = 0

    for path, blobstats in delta_tree.items():
        if path in previous_tree:
            delta_loc -= previous_tree[path].loc
            delta_cyclomatic_complexity -= previous_tree[path].cyclomaticComplexity
            delta_functions -= previous_tree[path].functions

        if blobstats:
            delta_loc += blobstats.loc
            delta_cyclomatic_complexity += blobstats.cyclomaticComplexity
            delta_functions += blobstats.functions

    return delta_loc, delta_cyclomatic_complexity, delta_functions

def aggregate_stats_from_blobs(blobs):
    total_loc = 0
    total_cyclomatic_complexity = 0
    total_functions = 0

    for blobname, blobstats in blobs.items():
        total_loc += blobstats.loc
        total_cyclomatic_complexity += blobstats.cyclomaticComplexity
        total_functions += blobstats.functions

    return total_loc, total_cyclomatic_complexity, total_functions

def apply_delta_to_tree(previous_tree, tree_delta):
    for path, blobstats in tree_delta.items():
        if not blobstats:
            previous_tree.pop(path, None)
        else:
            previous_tree[path] = blobstats

    return

def calculate_function_complexities(tree):
    function_complexities = {}
    for path, blob in tree.items():
        content = blob.data_stream.read().decode(codec, errorHandler)
        analyzer = lizard.FileAnalyzer(lizard.get_extensions([]))
        f = analyzer.analyze_source_code(blob.name, content)
        for function in f.function_list:
            function_complexities[path + "." + function.name] = function.cyclomatic_complexity

    return function_complexities
