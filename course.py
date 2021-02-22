class Course:
	"""
	Initializes the Course with a sequence of the cells from the WebSOC
	search results table. Note that these column numbers may change over
	each quarter.
	"""
	def __init__(self, columns):
		self.code   = columns[0]
		self.max    = columns[8]
		self.enr    = columns[9].split(" / ")[-1]
		self.wl     = columns[10]
		self.req    = columns[11]
		self.res    = ' '.join(chunk for chunk in columns[-4].split() if chunk != "and")
		self.units  = columns[3]

	def __str__(self):
		return f'Course code: {self.code}'

	def __repr__(self):
		return f'Course code: {self.code}'

	def __lt__(self, right):
		return int(self.code) < int(right.code)
