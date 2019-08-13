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

import git
import levenshtein
import sizeandcomplexity
import filters
from AnnotatedCommit import AnnotatedCommit

def analyzeNumberOfActiveDevelopers(data, activeCommitterInterval):
    print("Analyzing number of active developers per commit...", flush=True)
    for c in data:
        previous = c.previous
        cutOff = c.commit.committed_date - activeCommitterInterval
        committers = set()
        while previous is not None and previous.commit.committed_date > cutOff:
            committers.add(previous.commit.author.name)
            previous = previous.previous

        c.numberOfActiveDevelopers = len(committers)
    print("Done.", flush=True)

def analyzeDaysSincePreviousCommit(data, activeCommitterInterval):
    print("Analyzing days since previous commit by same developer...", flush=True)
    for c in data:
        previous = c.previous
        cutOff = c.commit.committed_date - activeCommitterInterval

        while previous is not None and previous.commit.committed_date > cutOff:
            if previous.commit.author.name == c.commit.author.name:
                c.daysSincePreviousCommitByDeveloper = int((c.commit.committed_date - previous.commit.committed_date) / (60 * 60 * 24))
                break
            previous = previous.previous

    print("Done.", flush=True)

def analyzeNumberOfCommitsInSameDay(data):
    print("Analyzing number of commits in same day...", flush=True)

    for c in data:
        previous = c.previous
        cutOff = c.commit.committed_date - 60 * 60 * 24
        c.numberOfCommitsInLast24h = 0

        while previous is not None and previous.commit.committed_date > cutOff:
            c.numberOfCommitsInLast24h += 1
            previous = previous.previous

    print("Done.", flush=True)

def analyzeLevenshteinDistance(data):
    print("Analyzing Levenshtein distance of commits...", flush=True)

    i = 0
    for c in data:
        i += 1
        if c.previous is None:
            continue

        print("    " + str(i) + "/" + str(len(data)) + " (" + c.commit.__str__() + ")", end="\r", flush=True)
        c.levenshteinDistance = levenshtein.commitDistance(c.commit)

    print("")
    print("Done.", flush=True)

def analyzeSizeAndComplexity(data):
    print("Analyzing size and complexity of commits...", flush=True)

    if len(data) == 0: return
    print("    Building baseline map of size and complexity stats...", flush=True)
    previous_commit = AnnotatedCommit(data[0].commit.parents[0])
    previous_tree = sizeandcomplexity.analyze_tree(previous_commit.commit.tree)
    previous_commit.loc, previous_commit.cyclomaticComplexity, previous_commit.functions = sizeandcomplexity.aggregate_stats_from_blobs(previous_tree)
    print("    Done (" + str(len(previous_tree)) + " blobs).", flush=True)

    print("    Analyzing size and complexity delta per commit...", flush=True)
    i = 0
    for c in data:
        i += 1
        print("    " + str(i) + "/" + str(len(data)) + " (" + c.commit.__str__() + ")", end="\r", flush=True),

        tree_delta = sizeandcomplexity.tree_delta(c.commit)

        delta_loc, delta_cyclomatic_complexity, delta_functions = sizeandcomplexity.aggregate_delta(previous_tree, tree_delta)

        c.loc = previous_commit.loc + delta_loc
        c.deltaLoc = delta_loc
        c.cyclomaticComplexity = previous_commit.cyclomaticComplexity + delta_cyclomatic_complexity
        c.deltaCyclomaticComplexity = delta_cyclomatic_complexity
        c.functions = previous_commit.functions + delta_functions
        c.deltaFunctions = delta_functions

        previous_commit = c
        sizeandcomplexity.apply_delta_to_tree(previous_tree, tree_delta)

    print("")
    print("Done.", flush=True)

def analyzeComplexFunctionsContributions(data, complex_functions):
    print("Analyzing contributions to complex functions...", flush=True)

    if len(data) == 0: return

    print("    Building baseline map of function complexities...", flush=True)
    previous_tree = sizeandcomplexity.all_blobs_in_tree(data[0].commit.parents[0].tree)
    previous_function_complexities = sizeandcomplexity.calculate_function_complexities(previous_tree)
    print("    Done (" + str(len(previous_tree)) + " blobs).", flush=True)

    i = 0
    for c in data:
        i += 1
        print("    " + str(i) + "/" + str(len(data)) + " (" + c.commit.__str__() + ")", end="\r", flush=True)

        modified_blobs = sizeandcomplexity.all_blobs_modified_by_commit(c.commit)
        for function, complexity in sizeandcomplexity.calculate_function_complexities(modified_blobs).items():
            if function in complex_functions:
                update_complex_function_contribution_of_commit(previous_function_complexities, function, complexity, c)

            previous_function_complexities[function] = complexity

        previous_commit = c

    print("")
    print("Done.", flush=True)

def update_complex_function_contribution_of_commit(previous_function_complexities, function, complexity, commit):
    previous_complexity = 0
    increase = 0
    decrease = 0
    if function in previous_function_complexities.keys():
        previous_complexity =  previous_function_complexities[function]

    if previous_complexity > 11 and previous_complexity > complexity:
        decrease = previous_complexity - complexity
        if commit.decreaseOfComplexityInComplexFunctions:
            commit.decreaseOfComplexityInComplexFunctions += decrease
        else:
            commit.decreaseOfComplexityInComplexFunctions = decrease

    if complexity > 11 and complexity > previous_complexity:
        increase = complexity - previous_complexity
        if commit.increaseOfComplexityInComplexFunctions:
            commit.increaseOfComplexityInComplexFunctions += increase
        else:
            commit.increaseOfComplexityInComplexFunctions = increase
