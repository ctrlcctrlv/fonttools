import DefaultTable
import struct, sstruct
from fontTools.misc.textTools import safeEval
import string
from types import FloatType, ListType, StringType, TupleType
import sys
METAHeaderFormat = """
		>	# big endian
		tableVersionMajor:			H
		tableVersionMinor:			H
		metaEntriesVersionMajor:	H
		metaEntriesVersionMinor:	H
		unicodeVersion:				L
		metaFlags:					H
		nMetaRecs:					H
"""
# This record is followed by nMetaRecs of METAGlyphRecordFormat.
# This in turn is followd by as many METAStringRecordFormat entries
# as specified by the METAGlyphRecordFormat entries
# this is followed by the strings specifried in the  METAStringRecordFormat
METAGlyphRecordFormat = """
		>	# big endian
		glyphID:			H
		nMetaEntry:			H
"""
# This record is followd by a variable data length field:
# 	USHORT or ULONG	hdrOffset	
# Offset from start of META table to the beginning
# of this glyphs array of ns Metadata string entries.
# Size determined by metaFlags field		
# METAGlyphRecordFormat entries must be sorted by glyph ID
 
METAStringRecordFormat = """
		>	# big endian
		labelID:			H
		stringLen:			H
"""
# This record is followd by a variable data length field:
# 	USHORT or ULONG	stringOffset	
# METAStringRecordFormat entries must be sorted in order of labelID
# There may be more than one entry with the same labelID
# There may be more than one strign with the same content.

# Strings shall be Unicode UTF-8 encoded, and null-terminated.

METALabelDict = {
	0 : "MojikumiX4051", # An integer in the range 1-20
	1 : "UNIUnifiedBaseChars",
	2 : "BaseFontName",
	3 : "Language",
	4 : "CreationDate",
	5 : "FoundryName",
	6 : "FoundryCopyright",
	7 : "OwnerURI",
	8 : "WritingScript",
	10 : "StrokeCount",
	11 : "IndexingRadical",
}


def getLabelString(labelID):
	try:
		label = METALabelDict[labelID]
	except KeyError:
		label = "Unknown label"
	return str(label)


class table_M_E_T_A_(DefaultTable.DefaultTable):
	
	dependencies = []
	
	def decompile(self, data, ttFont):
		dummy, newData = sstruct.unpack2(METAHeaderFormat, data, self)
		self.glyphRecords = []
		for i in range(self.nMetaRecs):
			glyphRecord, newData = sstruct.unpack2(METAGlyphRecordFormat, newData, GlyphRecord())
			if self.metaFlags == 0:
				[glyphRecord.offset] = struct.unpack(">H", newData[:2])
				newData = newData[2:]
			elif self.metaFlags == 1:
				[glyphRecord.offset] = struct.unpack(">H", newData[:4])
				newData = newData[4:]
			else:
				assert 0, "The metaFlags field in the META table header has a value other than 0 or 1 :" + str(self.metaFlags)
			glyphRecord.stringRecs = []
			newData = data[glyphRecord.offset:]
			for j in range(glyphRecord.nMetaEntry):
				stringRec, newData = sstruct.unpack2(METAStringRecordFormat, newData, StringRecord())
				if self.metaFlags == 0:
					[stringRec.offset] = struct.unpack(">H", newData[:2])
					newData = newData[2:]
				else:
					[stringRec.offset] = struct.unpack(">H", newData[:4])
					newData = newData[4:]
				stringRec.string = data[stringRec.offset:stringRec.offset + stringRec.stringLen]
				glyphRecord.stringRecs.append(stringRec)
			self.glyphRecords.append(glyphRecord)	
			
	def compile(self, ttFont):
		offsetOK = 0
		self.nMetaRecs = len(self.glyphRecords)
		count = 0
		while ( offsetOK != 1):
			count = count + 1
			if count > 4:
				pdb_set_trace()
			metaData = sstruct.pack(METAHeaderFormat, self)
			stringRecsOffset = len(metaData) + self.nMetaRecs * (6 + 2*(self.metaFlags & 1))
			stringRecSize = (6 + 2*(self.metaFlags & 1))
			for glyphRec in self.glyphRecords:
				glyphRec.offset = stringRecsOffset
				if (glyphRec.offset > 65535) and ((self.metaFlags & 1) == 0):
					self.metaFlags = self.metaFlags + 1
					offsetOK = -1
					break
				metaData = metaData + glyphRec.compile(self)
				stringRecsOffset = stringRecsOffset + (glyphRec.nMetaEntry * stringRecSize) 
				# this will be the String Record offset for the next GlyphRecord.
			if 	offsetOK == -1:
				offsetOK = 0
				continue
			
			# metaData now contains the header and all of the GlyphRecords. Its length should bw
			# the offset to the first StringRecord.
			stringOffset = stringRecsOffset
			for glyphRec in self.glyphRecords:
				assert (glyphRec.offset == len(metaData)), "Glyph record offset did not compile correctly! for rec:" + str(glyphRec)
				for stringRec in glyphRec.stringRecs:
					stringRec.offset = stringOffset
					if (stringRec.offset > 65535) and ((self.metaFlags & 1) == 0):
						self.metaFlags = self.metaFlags + 1
						offsetOK = -1
						break
					metaData = metaData + stringRec.compile(self)
					stringOffset = stringOffset + stringRec.stringLen
			if 	offsetOK == -1:
				offsetOK = 0
				continue
				
			if ((self.metaFlags & 1) == 1) and (stringOffset < 65536):
				self.metaFlags = self.metaFlags - 1
				continue
			else:
				offsetOK = 1
					
								
			# metaData now contains the header and all of the GlyphRecords and all of the String Records.
			# Its length should be the offset to the first string datum.
			for glyphRec in self.glyphRecords:
				for stringRec in glyphRec.stringRecs:
					assert (stringRec.offset == len(metaData)), "String offset did not compile correctly! for string:" + str(stringRec.string)
					metaData = metaData + stringRec.string
		
		return metaData
	
	def toXML(self, writer, ttFont):
		writer.comment("Lengths and number of entries in this table will be recalculated by the compiler")
		writer.newline()
		formatstring, names, fixes = sstruct.getformat(METAHeaderFormat)
		for name in names:
			value = getattr(self, name)
			writer.simpletag(name, value=value)
			writer.newline()
		for glyphRec in self.glyphRecords:
			glyphRec.toXML(writer, ttFont)
		
	def fromXML(self, (name, attrs, content), ttFont):
		if name == "GlyphRecord":
			if not hasattr(self, "glyphRecords"):
				self.glyphRecords = []
			glyphRec = GlyphRecord()
			self.glyphRecords.append(glyphRec)
			for element in content:
				if isinstance(element, StringType):
					continue
				glyphRec.fromXML(element, ttFont)
			glyphRec.offset = -1
			glyphRec.nMetaEntry = len(glyphRec.stringRecs)
		else:			
			value = attrs["value"]
			try:
				value = safeEval(value)
			except OverflowError:
				value = long(value)
			setattr(self, name, value)


class GlyphRecord:
	def __init__(self):
		self.glyphID = -1
		self.nMetaEntry = -1
		self.offset = -1
		self.stringRecs = []
		
	def toXML(self, writer, ttFont):
		writer.begintag("GlyphRecord")
		writer.newline()
		writer.simpletag("glyphID", value=self.glyphID)
		writer.newline()
		writer.simpletag("nMetaEntry", value=self.nMetaEntry)
		writer.newline()
		for stringRec in self.stringRecs:
			stringRec.toXML(writer, ttFont)
		writer.endtag("GlyphRecord")
		writer.newline()


	def fromXML(self, (name, attrs, content), ttFont):
		if name == "StringRecord":
			stringRec = StringRecord()
			self.stringRecs.append(stringRec)
			for element in content:
				if isinstance(element, StringType):
					continue
				stringRec.fromXML(element, ttFont)
			stringRec.stringLen = len(stringRec.string)
		else:			
			value = attrs["value"]
			try:
				value = safeEval(value)
			except OverflowError:
				value = long(value)
			setattr(self, name, value)

	def compile(self, parentTable):
		data = sstruct.pack(METAGlyphRecordFormat, self)
		if parentTable.metaFlags == 0:
			datum = struct.pack(">H", self.offset)
		elif parentTable.metaFlags == 1:
			datum = struct.pack(">L", self.offset)
		data = data + datum
		return data


	def __cmp__(self, other):
		"""Compare method, so a list of NameRecords can be sorted
		according to the spec by just sorting it..."""

		if type(self) != type(other) or \
		   self.__class__ != other.__class__:
			return cmp(id(self), id(other))

		return cmp(self.glyphID, other.glyphID)
	
	def __repr__(self):
		return "GlyphRecord[ glyphID: " + str(self.glyphID) + ", nMetaEntry: " + str(self.nMetaEntry) + ", offset: " + str(self.offset) + " ]"


def mapXMLToUTF8(string):
	uString = u""
	strLen = len(string)
	i = 0
	while i < strLen:
		prefixLen = 0
		if  (string[i:i+3] == "&#x"):
			prefixLen = 3
		elif  (string[i:i+7] == "&amp;#x"):
			prefixLen = 7
		if prefixLen:
			i = i+prefixLen
			j= i
			while string[i] != ";":
				i = i+1
			valStr = string[j:i]
			
			uString = uString + unichr(eval('0x' + valStr))
		else:
			uString = uString + unichr(ord(string[i]))
		i = i +1
			
	return uString.encode('utf8')


def mapUTF8toXML(string):
	uString = string.decode('utf8')
	string = ""
	for uChar in uString:
		i = ord(uChar)
		if (i < 0x80) and (i > 0x1F):
			string = string + chr(i)
		else:
			string = string + "&#x" + hex(i)[2:] + ";"
	return string


class StringRecord:
	def __init__(self):
		self.labelID = -1
		self.string = ""
		self.stringLen = -1
		self.offset = -1

	def toXML(self, writer, ttFont):
		writer.begintag("StringRecord")
		writer.newline()
		writer.simpletag("labelID", value=self.labelID)
		writer.comment(getLabelString(self.labelID))
		writer.newline()
		writer.newline()
		writer.simpletag("string", value=mapUTF8toXML(self.string))
		writer.newline()
		writer.endtag("StringRecord")
		writer.newline()

	def fromXML(self, (name, attrs, content), ttFont):
		value = attrs["value"]
		if name == "string":
			self.string = mapXMLToUTF8(value)
		else:
			try:
				value = safeEval(value)
			except OverflowError:
				value = long(value)
			setattr(self, name, value)

	def compile(self, parentTable):
		data = sstruct.pack(METAStringRecordFormat, self)
		if parentTable.metaFlags == 0:
			datum = struct.pack(">H", self.offset)
		elif parentTable.metaFlags == 1:
			datum = struct.pack(">L", self.offset)
		data = data + datum
		return data

	def __cmp__(self, other):
		"""Compare method, so a list of NameRecords can be sorted
		according to the spec by just sorting it..."""

		if type(self) != type(other) or \
		   self.__class__ != other.__class__:
			return cmp(id(self), id(other))

		return cmp(self.labelID, other.labelID)
	
	def __repr__(self):
		return "StringRecord [ labelID: " + str(self.labelID) + " aka " + getLabelString(self.labelID) \
			+ ", offset: " + str(self.offset) + ", length: " + str(self.stringLen) + ", string: " +self.string + " ]"

