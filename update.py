# Copyright (c) 2011 Julian Wintermayr
# 
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
# 
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE
# LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
# WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.


import grab
import urllib2
import urllib
import search


class Updater:
	"""
	Class for updating the local database from the Mathematics Genealogy Project.
	Update-by-ID and Update-by-name implemented.
	Can find the corresponding ID to a last name.
	"""
	def __init__(self, connector, naive, web):
		self.pagestr = None
		self.foundID = False
		self.foundIDs = []
		self.naiveMode = naive
		self.webMode = web

		# The Grabber returns only for the students a set and not for the advisors as the advisors need to be
		# ordererd to separate different advisor sets
		self.currentAdvisorsGrab = []
		self.currentStudentsGrab = set()

		self.connector = connector
		self.connection = connector[0]
		self.cursor = connector[1]


	def getSearchPage(self, lastName):
		try:
			# Get the raw data of this site. Return an object of class 'http.client.HTTPResponse'
			page = urllib2.urlopen("http://genealogy.math.ndsu.nodak.edu/query-prep.php",
									urllib.urlencode({"family_name":lastName}).encode("utf-8"))

			# Read the raw data and return an object of class 'bytes' (html-code)
			self.pagestr = page.read()

			# Convert bytes-string to readable UTF-8 html-code of class 'str'
			self.pagestr = self.pagestr.decode("utf-8")

		except urllib2.URLError:
			print(u"URLError: Try to get page again.".encode('utf-8'))
			self.getSearchPage(lastName)


	def findID(self, lastName):
		"""
		Find the corresponding ID of a mathematician listed in the
		Mathematics Genealogy Project. This ID is needed to run Update-by-ID.
		"""
		self.getSearchPage(lastName)

		# Split the page string at newline characters to get single lines.
		psarray = self.pagestr.split("\n")

		if self.webMode:
			lines = iter(psarray)

			# Iterate through every line of the html-code.
			for line in lines:
				if 'a href=\"id.php?id=' in line:
					# Store if there are mathematicians with that entered last name.
					self.foundID = True

					# Extract ID of found mathematicians.
					idAndName = line.split('a href=\"id.php?id=')[1]
					id = int(idAndName.split('\">')[0])
					name = grab.Grabber.unescape(idAndName.split('\">')[1].split('</a>')[0].strip())

					line = next(lines)

					uni = grab.Grabber.unescape(line.split('<td>')[1].split('</td>')[0].strip())

					if uni == "":
						uni = None

					line = next(lines)

					year = grab.Grabber.unescape(line.split('<td>')[1].split('</td>')[0].strip())

					if year == "":
						year = None

					print(u"{};{};{};{}".format(id, name, uni, year).encode('utf-8'))

		else:
			# Iterate through every line of the html-code.
			for line in psarray:
				if 'a href=\"id.php?id=' in line:
					# Store if there are mathematicians with that entered last name.
					self.foundID = True

					# Extract ID of found mathematicians.
					id = int(line.split('a href=\"id.php?id=')[1].split('\">')[0])
					self.foundIDs.append(id)

			if self.foundID:
				# Print every found mathematician and store them in the local database.
				for id in self.foundIDs:
					[name, uni, year, advisors, students, dissertation, numberOfDescendants] = self.grabNode(id)
					print(u"ID: {}  Name: {}  University: {}  Year: {}".format(id, name, uni[0], year[0]).encode('utf-8'))
					self.insertOrUpdate(id, name, uni, year, advisors, dissertation, numberOfDescendants)

		if not self.foundID:
			print(u"There is either no mathematician in the online-database with that entered last name or there are too many. \
					You can check http://genealogy.math.ndsu.nodak.edu/search.php though and try to find the desired mathematician \
					by using more search options. You can then use the ID of this mathematician to run Update-by-ID.".encode('utf-8'))


	def insertOrUpdate(self, id, name, unis, years, advisors, dissertations, numberOfDescendants):
		"""
		Update or create entries in the tables mathematicians, advised and dissertation of the local database.
		Replace existing mathematicians.
		"""
		self.cursor.execute("DELETE FROM dissertation WHERE author=?", (id,))
		self.connection.commit()

		self.cursor.execute("INSERT INTO person VALUES (?, ?, ?)",  (id, name, numberOfDescendants))
		self.connection.commit()

		advOrder = 0

		# Create iterators.
		iterAdvisor = iter(advisors)
		iterUni = iter(unis)
		iterYear = iter(years)

		# The lists dissertation, uni and year have the same length. The items are either set or None.
		# Hence, iterating one of them is enough to avoid range errors.
		for dissertation in dissertations:
			uni = next(iterUni)
			year = next(iterYear)

			self.cursor.execute("INSERT INTO dissertation VALUES (NULL, ?, ?, ?, ?)", (id, dissertation, uni, year))
			self.connection.commit()
			did = self.cursor.lastrowid

			for advID in iterAdvisor:
				# If advisors are separated by 0, then a new set of advisors starts
				# which means, that there is also another dissertation.
				# Hence, the order must be reset and the next set of advisors must be grabbed.
				if advID == 0:
					advOrder = 0
					break

				advOrder += 1
				self.cursor.execute("INSERT INTO advised VALUES (?, ?, ?)",  (did, advOrder, advID))
				self.connection.commit()


	def grabNode(self, id):
		"""
		Use the Grabber class to grab all stored information of a mathematician from
		the Mathematics Genealogy Project and return them.
		"""
		try:
			grabber = grab.Grabber(id)

			# foundID indicates that the program runs in Update-by-Name mode. Following output
			# is disturbing in this mode.
			if not self.foundID:
				print(u"\nGrabbing record #{}:".format(id).encode('utf-8'))

			[name, uni, year, advisors, students, dissertation, numberOfDescendants] = grabber.extractNodeInformation()

			if not self.foundID:
				print(u"Name: {}  University: {}  Year: {}".format(name, uni[0], year[0]).encode('utf-8'))

		except ValueError:
			# The given id does not exist in the Math Genealogy Project.
			raise

		except IndexError:
			print(u"Index Error: Grab again.".encode('utf-8'))
			return self.grabNode(id)

		return [name, uni, year, advisors, students, dissertation, numberOfDescendants]


	def recursiveAncestors(self, advisors):
		"""
		Take the advisor list and grab them recursively.
		Grabbed advisors will be stored in a separate list to avoid grabbing the same ID several times.
		"""
		for advisor in advisors:
			# ID=0 just indicates that a new set of advisors begins here. ID=0 shouldn't be grabbed.
			if advisor == 0:
				continue

			[name, uni, year, nextAdvisors, nextStudents, dissertation, numberOfDescendants] = self.grabNode(advisor)
			self.currentAdvisorsGrab.append(advisor)
			self.insertOrUpdate(advisor, name, uni, year, nextAdvisors, dissertation, numberOfDescendants)

			# Smart update not possible for ancestors as the number of all ancestors isn't stored online.

			ungrabbedAdvisors = []

			if len(nextAdvisors) > 0:
				for nextAdvisor in nextAdvisors:
					if nextAdvisor not in self.currentAdvisorsGrab:
						ungrabbedAdvisors.append(nextAdvisor)

				self.recursiveAncestors(ungrabbedAdvisors)


	def recursiveDescendants(self, students):
		"""
		Take the student list and grab them recursively.
		Grabbed students will be stored in a separate list to avoid grabbing the same ID several times.
		"""
		for student in students:
			[name, uni, year, nextAdvisors, nextStudents, dissertation, numberOfDescendants] = self.grabNode(student)
			self.currentStudentsGrab.add(student)

			# Update before comparing numbers because the comparing checks only if the
			# descendants are in the database and not if the current mathematician is in it.
			self.insertOrUpdate(student, name, uni, year, nextAdvisors, dissertation, numberOfDescendants)

			if not self.naiveMode and self.smartUpdate(student, numberOfDescendants):
				continue

			if len(nextStudents) > 0:
				self.recursiveDescendants(nextStudents.difference(self.currentStudentsGrab))


	def updateByID(self, ids, ancestors, descendants):
		"""
		Grab the given ID(s) and grab their ancestors and/or descendants and update their paths.
		"""
		for id in ids:
			[name, uni, year, advisors, students, dissertation, numberOfDescendants] = self.grabNode(id)
			self.insertOrUpdate(id, name, uni, year, advisors, dissertation, numberOfDescendants)

			if ancestors:
				self.recursiveAncestors(advisors)

			if descendants:
				if not self.naiveMode and self.smartUpdate(id, numberOfDescendants):
					continue

				self.recursiveDescendants(students)


	def smartUpdate(self, id, onlineNumber):
		"""
		Compare online stored number of descendants with calculated number of descendants
		given by the advised-table.
		If numbers are equal, no mathematician has been added and no update is needed.
		"""
		self.cursor.execute("SELECT author FROM advised, dissertation WHERE student=dID AND advisor=?", (id,))
		localStudents = self.cursor.fetchall()

		print(u"Online descendants = {}".format(onlineNumber).encode('utf-8'))

		if len(localStudents) > 0:
			storedStudents = set()

			for row in localStudents:
				storedStudents.add(row["author"])

			searcher = search.Searcher(self.connector, False, False)
			calculatedNumber = searcher.numberOfDescendants(storedStudents)

			if calculatedNumber == onlineNumber:
				print(u"In local database = {}".format(calculatedNumber).encode('utf-8'))
				print(u"Skip branch!".encode('utf-8'))

				return True

			else:
				print(u"In local database >= {}".format(calculatedNumber).encode('utf-8'))

			if calculatedNumber > onlineNumber:
				print(u"Student(s) online deleted! Delete them in local database and grab this branch again.".encode('utf-8'))

				for delStudent in storedStudents:
					self.cursor.execute("DELETE FROM dissertation WHERE author=?", (delStudent,))
					# TRIGGER and CASCADE statements will delete the entries in the other tables
					self.connection.commit()

		elif len(localStudents) == 0 and onlineNumber < 2:
			print(u"In local database = 0".encode('utf-8'))

		else:
			print(u"In local database: N/A".encode('utf-8'))

		return False