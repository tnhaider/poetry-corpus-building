import sys, json, re
from langdetect import detect_langs
from random import shuffle
from nltk import bigrams
import joblib
import json
from inout.dta.corpus import Corpus
from inout.dta.document import Document
from inout.dta.poem import Poem
from hyphenation.syllabifier import Syllabifier
from somajo import SoMaJo
tokenizer = SoMaJo("de_CMC", split_camel_case=True)
syllabifier = Syllabifier()

def normalize_characters(text):
	text = re.sub('<[^>]*>', '', text)
	text = re.sub('ſ', 's', text)
	if text.startswith("b'"):
		text = text[2:-1]
	text = re.sub('&#223;', 'ß', text)
	text = re.sub('&#383;', 's', text)
	text = re.sub('u&#868;', 'ü', text)
	text = re.sub('a&#868;', 'ä', text)
	text = re.sub('o&#868;', 'ö', text)
	text = re.sub('&#246;', 'ö', text)
	text = re.sub('&#224;', 'a', text) # quam with agrave
	text = re.sub('&#772;', 'm', text) # Combining Macron in kom772t
	text = re.sub('&#8217;', "'", text)
	text = re.sub('&#42843;', "r", text) # small rotunda
	text = re.sub('&#244;', "o", text) # o with circumflex (ocr)
	text = re.sub('&#230;', "ae", text) 
	text = re.sub('&#8229;', '.', text) # Two Dot Leader ... used as 'lieber A.'
	text = re.sub('Jch', 'Ich', text)
	text = re.sub('Jst', 'Ist', text)
	text = re.sub('JCh', 'Ich', text)
	text = re.sub('jch', 'ich', text)
	text = re.sub('Jn', 'In', text)
	text = re.sub('DJe', 'Die', text)
	text = re.sub('Wje', 'Wie', text)
	text = re.sub('¬', '-', text) # negation sign
	#text = re.sub('Jn', 'In', text)
	text = text.encode("utf-8", 'replace')
	#text = text.decode("utf-8", 'replace')
	text = re.sub(b'o\xcd\xa4', b'\xc3\xb6', text) # ö
	text = re.sub(b'u\xcd\xa4', b'\xc3\xbc', text) # ü
	text = re.sub(b'a\xcd\xa4', b'\xc3\xa4', text) # ä
	text = re.sub(b'&#771;', b'\xcc\x83', text) # Tilde
	text = re.sub(b'&#8222;', b'\xe2\x80\x9d', text) # Lower Quot Mark
	text = re.sub(b'\xea\x9d\x9b', b'r', text) # small Rotunda
	text = re.sub(b'\xea\x9d\x9a', b'R', text) # big Rotunda
	text = text.decode('utf-8')
	ftl = text[:2] # check if first two letters are capitalized
	try:
		if ftl == ftl[:2].upper():
			text = ftl[0] + ftl[1].lower() + text[2:]
	except IndexError:
		pass
	return text


def get_syllables_caesuras(line):
	line = str(line)
	line = re.sub('\(', '', line)
	line = re.sub('\)', '', line)	
	bi = list(bigrams(line))
	syllables = []
	caesuras = []
	for i, j in bi:
		if j == '|':
			caesuras.append(':')
		else:
			caesuras.append('.')
		if i != '|':
			syllables.append(i)
	return syllables, caesuras
			

def jsonpoem():
	jpoem = {
	'metadata':{
	'author' : 
		{
		'name' : 'N.A.', #author_name,
		'birth': 'N.A.', #birthyear, 
		'death': 'N.A.', #deathyear,
		},
	'title' : 'N.A.', #title,
	'genre' : 'N.A.', #genre,
	'period' : 'N.A.', #period,
	'pub_year': 'N.A.', #year,
	'urn': 'N.A.', #year,
	'language': 'N.A.', #year,
	},
	'text': None, #year,
	}
	return jpoem

def construct_json(poem, pos_model):
	jpoem = jsonpoem()
	author = poem.get_author()
	if len(author.strip()) < 3:
		print("NO AUTHOR -- QUITTING")
		return None
	jpoem['metadata']['author']['name'] = poem.get_author()
	jpoem['metadata']['title'] = normalize_characters(poem.get_title())
	jpoem['metadata']['pub_year'] = poem.get_year()
	jpoem['metadata']['genre'] = poem.get_genre()
	jpoem['metadata']['urn'] = poem.get_urn()
	jpoem['poem'] = {}
	#print()
	#print(author)
	#print(year)
	#print(title)
	#print(period)
	s = 1
	for stanza in poem.get_stanzas():
		stanza_id = 'stanza.' + str(s)
		jstanza = {}
		l = 1
		for line in stanza.get_line_objects():
			line_id = 'line.' + str(l)
			jline = {}
			linetext = str(line.get_text())
			linetext = normalize_characters(linetext)
			#print()
			#print(linetext)
			jline['text'] = linetext
			#print(linetext)
			#linemeter = line.get_meter()
			#print(get_syllables_caesuras(linemeter))
			#linerhythm = line.get_rhythm()
			tokenized = tokenizer.tokenize_text([linetext])
			#print(list(tokenized))
			tokens = []
			token_classes = []
			for sentence in tokenized:
				for token in sentence:
					try:
						tokens.append(str(token.text))
						token_classes.append(str(token.token_class))
					except:
						continue
			#print(tokens)
			try:
				tokens, token_classes = remove_stanza_numbers(tokens, token_classes)
			except IndexError:
				continue
			l +=1
			token_classes = replace_token_class(token_classes)
			pos = get_pos_sequence(tokens, pos_model)
			#jline['tokens'] = tokens
			syllables = []
			for token in tokens:
				try:
					word_syllables = syllabifier.predict(token)
					syllables.append(word_syllables)
				except IndexError:
					print(linetext)
					print(tokenized)
					print(tokens)
			#print(syllables)
			#print(token_classes)
			#print()
			jline['tokens'] = syllables
			jline['token_info'] = token_classes
			jline['pos'] = pos
			jstanza[line_id] = jline
		if not jstanza:
			continue
		s += 1
		jpoem['poem'][stanza_id] = jstanza
	#print(jpoem['metadata'])
	return jpoem	


			#group[sid].append((linetext, linemeter, linerhythm, tokens, syllables))
			#print(l, linetext)
	#print(group)

def replace_token_class(class_list):
	new_list = []
	for i in class_list:
		if i == 'regular':
			new_list.append('word')
		elif i == 'symbol':
			new_list.append('punct')
		else:
			new_list.append(i)
	return new_list

def remove_stanza_numbers(tokenized_line, token_classes):
	if re.match("^[0-9]", tokenized_line[0][0]):
		return tokenized_line[1:], token_classes[1:]
	else:
		return tokenized_line, token_classes


def get_pos_sequence(tokenized_line, pos_model):
        #tokenized_line = tokenizer.tokenize(string_line)
        tokenized_line = [(i, '') for i in tokenized_line]
        sent_features = sent2features(tokenized_line)
        pos = pos_model.predict([sent_features])[0]
        return pos

def word2features(sentence, index):
        word = sentence[index][0]
        postag = sentence[index][1]
        features = {
        # uebernommen vom DecisionTreeClassifier
                'word': word,
                'position_in_sentence': index,
                'rel_position_in_sentence': index / len(sentence),
                'is_first': index == 0,
                'is_last': index == len(sentence) - 1,
                'is_capitalized': word[0].upper() == word[0],
                'next_capitalized': '' if index == len(sentence) -1 else sentence[index+1][0].upper() == sentence[index+1][0],
                'last_capitalized': '' if index == 0 else sentence[index-1][0].upper() == sentence[index-1][0],
                'is_all_caps': word.upper() == word,
                'is_all_lower': word.lower() == word,
                'prefix-1-low': word[0].lower(),
                'prefix-1': word[0],
                'prefix-2': word[:2],
                'prefix-3': word[:3],
                'prefix-4': word[:4],
                'suffix-1': word[-1],
                'suffix-2': word[-2:],
                'suffix-3': word[-3:],
                'suffix-4': word[-4:],
                'prev_word': '' if index == 0 else sentence[index-1][0],
                'prev_prev_word': '' if index == 0 or index == 1 else sentence[index-2][0],
                'next_word': '' if index == len(sentence) - 1 else sentence[index + 1][0],
                'next_next_word': '' if index == len(sentence) - 1 or index == len(sentence) -2  else sentence[index + 2][0],
                #'prev_tag': '' if index == 0 else sentence[index-1][1],
                #'next_tag': '' if index == len(sentence)-1 else sentence[index+1][1],
                'has_hyphen': '-' in word,
                'is_numeric': word.isdigit(),
                'capitals_inside': word[1:].lower() != word[1:]
        }
        return features


def sent2features(sentence):
        return [word2features(sentence, i) for i in range(len(sentence))]




if __name__ == "__main__":
	#d = {}
	metadata_file = open('dta.metadaten.log', 'w', buffering=5)
	json_file_name = 'dta.german.poetry.json'
	json_file = open(json_file_name, 'w')
	c = Corpus(sys.argv[1], debug=True)
	poems = c.read_poems()
	#shuffle(poems)
	pos_model = joblib.load(sys.argv[2])

	dta_dict = {}
	c = 0
	for poem in poems:
		c += 1
		poem_id = 'dta.poem.' + str(c)
		#print(c)
		#print('Constructing .json')
		jpoem = construct_json(poem, pos_model)
		try:
			language = detect_langs(jpoem['poem']['stanza.1']['line.1']['text'])
			langs = []
			for lang in language:
				langs.append(str(lang)[:7])
				#print(str(lang))
			jpoem['metadata']['language'] = langs
		except:
			jpoem['metadata']['language'] = 'unknown'
		if jpoem['poem'] == {}:
			print('************************************************************')
			print('------------------------------------------------------------')
			print('************************************************************')
			print('************************************************************')
			print('************************************************************')
			print(jpoem)
			print('************************************************************')
			print('************************************************************')
			print('************************************************************')
			print('************************************************************')
			print('************************************************************')
			#print(jpoem)
			#sys.exit('POEM BROKEN')
			continue
		try:
			dta_dict[poem_id] = jpoem
			#print(jpoem['metadata'])
			#metadata_file.write(str(jpoem['metadata']))
			#metadata_file.write('\n')
			#metadata_file.write(str(jpoem['poem']['stanza.1']['line.1']))
			#metadata_file.write('\n\n')
		except KeyError:
			print('************************************************************')
			print('************************************************************')
			print('************************************************************')
			print('************************************************************')
			print('************************************************************')
			print(jpoem)
			print('************************************************************')
			print('************************************************************')
			print('************************************************************')
			print('************************************************************')
			print('************************************************************')
			#sys.exit('POEM BROKEN')
			continue
	print('DONE!')
	print('Loading Dictionary to ' + json_file_name)
	json.dump(dta_dict, json_file)
	print('Finished.')

