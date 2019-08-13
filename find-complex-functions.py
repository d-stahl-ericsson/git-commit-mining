#!/usr/bin/env python

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

import csv
import sys
import os
import string
import operator
import getopt
import datetime
import time
import git
from AnnotatedCommit import AnnotatedCommit
import gitanalyses
import argparse
import filters
import lizard
import extensions

def error(message):
    print(message)
    sys.exit(1)

def getRepository(repoDir):
    try:
        return git.Repo(repoDir)
    except git.exc.InvalidGitRepositoryError:
        error("Could not find valid repository in " + repoDir + ". Run in the root directory of a valid Git repository or use the --branch argument to identify one.")

def secondsToIso(seconds):
    return datetime.date.fromtimestamp(seconds).isoformat()

def parseStartTime(arg):
    try:
        start = datetime.datetime.strptime(arg, "%Y-%m-%d")
        epoch = datetime.datetime.utcfromtimestamp(0)
        return (start - epoch).total_seconds()
    except ValueError:
        error("Bad startTime format. Please specify a startTime on yyyy-mm-dd format.")

def parseEndTime(startTime, arg):
    return max(startTime, startTime + int(arg) * 60 * 60 * 24)

def parseActiveCommiterInterval(arg):
    return max(0, int(arg) * 60 * 60 * 24)

def createDataSet(repo, branch, startTime, endTime, activeCommitterInterval, filtered_authors, filtered_commits):
    print("Creating data set...", flush=True)
    try:
        rawCommits = list(reversed(list(repo.iter_commits(branch))))
    except git.exc.GitCommandError as e:
        error("Git command failed: {0}".format(e))

    data = list()
    current = None
    previous = None
    for i in range(len(rawCommits)):
        previous = current
        current = AnnotatedCommit(rawCommits[i])
        current.previous = previous
        if previous is not None:
            previous.next = current

        if current.commit.committed_date > startTime and current.commit.committed_date < endTime and len(current.commit.parents) == 1 and not filters.filter_match(current.commit, filtered_authors, filtered_commits):
            data.append(current)

    if len(data) == 0:
        error("No commits found on " + branch + " in the interval from " + secondsToIso(startTime) + " to " + secondsToIso(endTime) + ".")

    print("Done.", flush=True)
    return data

def tabulate(complex_functions):
    print("Tabulating...", flush=True)

    table = []
    table.append(("Function", "Max Complexity"))
    for f, c in complex_functions.items():
        table.append((f, c))

    print("Done.", flush=True)
    return table

def report(table, output):
    with open(output, "w+", encoding="utf-8") as f:
        csv.writer(f, lineterminator="\n").writerows(table)

def gitlyze(repoDir, branch, startTime, endTime, activeCommitterInterval, filtered_authors, filtered_commits, filtered_files):
    repo = getRepository(repoDir)
    data = createDataSet(repo, branch, startTime, endTime, activeCommitterInterval, filtered_authors, filtered_commits)

    complex_functions = find_complex_functions(data, filtered_files)

    print("All done!", flush=True)

    return tabulate(complex_functions)

def find_complex_functions(data, filtered_files):
    print("Finding complex functions...", flush=True)

    complex_functions = {}
    first_commit = True
    i = 0

    for c in data:
        i += 1
        blobs_to_scan = []
        if i == 1:
            append_blobs(blobs_to_scan, c.commit.tree)
        else:
            for diff in c.commit.parents[0].diff(c.commit):
                if diff.b_blob and extensions.extension_supported(diff.b_blob.path):
                    blobs_to_scan.append(diff.b_blob)

        print("    " + str(i) + "/" + str(len(data)) + " (" + c.commit.__str__() + ", " + str(len(blobs_to_scan)) + " blobs)      ", end="\r", flush=True),

        for blob in blobs_to_scan:
            if blob.path in filtered_files: continue
            content = blob.data_stream.read().decode("utf-8", "backslashreplace")
            f = lizard.FileAnalyzer(lizard.get_extensions([])).analyze_source_code(blob.name, content)

            for function in f.function_list:
                if function.cyclomatic_complexity > 15:
                    distinguished_function_name = blob.path + "." + function.name
                    if distinguished_function_name in complex_functions:
                        complex_functions[distinguished_function_name] = max(function.cyclomatic_complexity, complex_functions[distinguished_function_name])
                    else:
                        complex_functions[distinguished_function_name] = function.cyclomatic_complexity

    print("")
    print("Done.", flush=True)
    return complex_functions

def append_blobs(blobs, tree):
    for blob in tree.blobs:
        if extensions.extension_supported(blob.path):
            blobs.append(blob)

    for subtree in tree.trees:
        append_blobs(blobs, subtree)

def main():
    repoDir = os.getcwd()
    branch = None
    startTimeArg = "2018-01-01"
    intervalArg = 365
    activeCommitterIntervalArg = 30
    output = None
    filtered_authors = []
    filtered_commits = []
    filtered_files = []

    parser = argparse.ArgumentParser()

    parser.add_argument('-b', help='The branch to analyze.', required=True)
    parser.add_argument('-d', help='The repository directory. Defaults to current working directory.')
    parser.add_argument('-s', help='Analysis start time. Defaults to 2018-01-01.')
    parser.add_argument('-i', type=int, help='Analysis interval, days. Defaults to 365.')
    parser.add_argument('-a', type=int, help='Active commiter interval, days. Defaults to 30.')
    parser.add_argument('-o', help='Output filename.', required=True)
    parser.add_argument('-af', type=str, help='Any author(s) to filter from the data. May be used multiple times.', action='append')
    parser.add_argument('-cf', type=str, help='Any commit(s) to filter from the data. May be used multiple times.', action='append')
    parser.add_argument('-ff', type=str, help='Any file(s) to filter from the data. May be used multiple times.', action='append')

    for key, value in parser.parse_args()._get_kwargs():
        if key == 'b': branch = value
        if key == 'd' and value is not None: repoDir = os.path.abspath(value)
        if key == 's' and value is not None: startTimeArg = value
        if key == 'i' and value is not None: intervalArg = value
        if key == 'a' and value is not None: activeCommitterInterval = value
        if key == 'o': output = value
        if key == 'af' and value is not None: filtered_authors = value
        if key == 'cf' and value is not None: filtered_commits = value
        if key == 'ff' and value is not None: filtered_files = value

    startTime = parseStartTime(startTimeArg)
    endTime = parseEndTime(startTime, intervalArg)
    activeCommitterInterval = parseActiveCommiterInterval(activeCommitterIntervalArg)
    report(gitlyze(repoDir, branch, startTime, endTime, activeCommitterInterval, filtered_authors, filtered_commits, filtered_files), output)

main()
