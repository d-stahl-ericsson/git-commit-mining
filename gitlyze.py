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

def tabulate(data, activeCommitterInterval, filtered_authors, filtered_commits):
    print("Tabulating...", flush=True)

    table = []
    activeCommitterIntervalDays = str(int(activeCommitterInterval / (24 * 60 * 60)))
    table.append(("Commit", "Author name", "Commit timestamp", "Committed date", "Number of active developers (" + str(activeCommitterIntervalDays) + " days)", "Days since previous commit by developer (up to " + str(activeCommitterIntervalDays) + " days)", "Number of commits in last 24h", "Levenshtein distance", "Lines of code", "Cyclomatic complexity", "Number of functions", "Delta lines of code", "Delta cyclomatic complexity", "Delta number of functions", "Increase in complex functions", "Decrease in complex functions"))
    for c in data:
        if c.levenshteinDistance == 0: continue
        authorname = ''.join(c for c in c.commit.author.name.lower() if c.isalnum())
        table.append((c.commit.__str__(), authorname, c.commit.committed_date, secondsToIso(c.commit.committed_date), c.numberOfActiveDevelopers, c.daysSincePreviousCommitByDeveloper, c.numberOfCommitsInLast24h, c.levenshteinDistance, c.loc, c.cyclomaticComplexity, c.functions, c.deltaLoc, c.deltaCyclomaticComplexity, c.deltaFunctions, c.increaseOfComplexityInComplexFunctions, c.decreaseOfComplexityInComplexFunctions))

    print("Done.", flush=True)
    return table

def report(table, output):
    with open(output, "w+", encoding="utf-8") as f:
        csv.writer(f, lineterminator="\n").writerows(table)

def gitlyze(repoDir, branch, startTime, endTime, activeCommitterInterval, filtered_authors, filtered_commits, complex_functions):
    repo = getRepository(repoDir)
    data = createDataSet(repo, branch, startTime, endTime, activeCommitterInterval, filtered_authors, filtered_commits)

    gitanalyses.analyzeNumberOfActiveDevelopers(data, activeCommitterInterval)
    gitanalyses.analyzeDaysSincePreviousCommit(data, activeCommitterInterval)
    gitanalyses.analyzeNumberOfCommitsInSameDay(data)
    gitanalyses.analyzeLevenshteinDistance(data)
    gitanalyses.analyzeSizeAndComplexity(data)
    gitanalyses.analyzeComplexFunctionsContributions(data, complex_functions)

    print("All done!", flush=True)

    return tabulate(data, activeCommitterInterval, filtered_authors, filtered_commits)

def parse_complex_functions_file(path):
    complex_functions = []
    with open(path, 'r') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            complex_functions.append(row["Function"])

    return complex_functions

def main():
    repoDir = os.getcwd()
    branch = None
    startTimeArg = "2018-01-01"
    intervalArg = 365
    activeCommitterIntervalArg = 30
    output = None
    filtered_authors = []
    filtered_commits = []
    complex_functions = []

    parser = argparse.ArgumentParser()

    parser.add_argument('-b', help='The branch to analyze.', required=True)
    parser.add_argument('-d', help='The repository directory. Defaults to current working directory (and some of the analyses will currently not work otherwise, sorry!).')
    parser.add_argument('-s', help='Analysis start time. Defaults to ' + startTimeArg + '.')
    parser.add_argument('-i', type=int, help='Analysis interval, days. Defaults to ' + str(intervalArg) + '.')
    parser.add_argument('-a', type=int, help='Active commiter interval, days. Defaults to ' + str(activeCommitterIntervalArg) + '.')
    parser.add_argument('-o', help='Output filename.', required=True)
    parser.add_argument('-af', type=str, help='Any author(s) to filter from the data. May be used multiple times.', action='append')
    parser.add_argument('-cf', type=str, help='Any commit(s) to filter from the data. May be used multiple times.', action='append')
    parser.add_argument('-cc', type=str, help='Complex functions .csv file.')

    for key, value in parser.parse_args()._get_kwargs():
        if key == 'b': branch = value
        if key == 'd' and value is not None: repoDir = os.path.abspath(value)
        if key == 's' and value is not None: startTimeArg = value
        if key == 'i' and value is not None: intervalArg = value
        if key == 'a' and value is not None: activeCommitterInterval = value
        if key == 'o': output = value
        if key == 'af' and value is not None: filtered_authors = value
        if key == 'cf' and value is not None: filtered_commits = value
        if key == 'cc' and value is not None: complex_functions = parse_complex_functions_file(os.path.abspath(value))

    startTime = parseStartTime(startTimeArg)
    endTime = parseEndTime(startTime, intervalArg)
    activeCommitterInterval = parseActiveCommiterInterval(activeCommitterIntervalArg)
    report(gitlyze(repoDir, branch, startTime, endTime, activeCommitterInterval, filtered_authors, filtered_commits, complex_functions), output)

main()
