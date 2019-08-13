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

class AnnotatedCommit:
    def __init__(self, commit):
        self.commit = commit
        self.numberOfActiveDevelopers = None
        self.daysSincePreviousCommitByDeveloper = None
        self.numberOfCommitsInLast24h = None
        self.levenshteinDistance = None
        self.loc = None
        self.deltaLoc = None
        self.cyclomaticComplexity = None
        self.deltaCyclomaticComplexity = None
        self.increaseOfComplexityInComplexFunctions = None
        self.decreaseOfComplexityInComplexFunctions = None
        self.functions = None
        self.deltaFunctions = None
        self.previous = None
        self.next = None
