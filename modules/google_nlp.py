# Copyright © 2025 Sid Ahmed KHETTAB
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/agpl-3.0.html>.

import os
import json
import pandas as pd
from flask import current_app, g
from .db import load_json_data, save_google_nlp_to_database, load_csv_data, get_project_file, load_text_data, update_nlp_state, update_genre_state, save_genre_and_main_idea
from .gemini import get_genre_and_main_idea
from google.cloud import language_v1





'''
# Translations
parts_of_speech = ['N/A', 'ADJ', 'ADP', 'ADV', 'CONJ', 'DET', 'NOUN', 'NUM', 'PRON', 'PRT', 'PUNCT', 'VERB', 'X', 'AFFIX']
numbers = ['N/A', 'SINGULAR', 'PLURAL', 'DUAL']
propers = ['N/A', 'PROPER', 'NOT_PROPER']
aspects = ['N/A', 'PERFECTIVE', 'IMPERFECTIVE', 'PROGRESSIVE']
cases = ['N/A', 'ACCUSATIVE', 'ADVERBIAL', 'COMPLEMENTIVE', 'DATIVE', 'GENITIVE', 'INSTRUMENTAL', 'LOCATIVE', 'NOMINATIVE', 'OBLIQUE', 'PARTITIVE', 'PREPOSITIONAL', 'REFLEXIVE_CASE', 'RELATIVE_CASE', 'VOCATIVE']
forms = ['N/A', 'ADNOMIAL', 'AUXILIARY', 'COMPLEMENTIZER', 'FINAL_ENDING', 'GERUND', 'REALIS', 'IRREALIS', 'SHORT', 'LONG', 'ORDER', 'SPECIFIC']
genders = ['N/A', 'FEMININE', 'MASCULINE', 'NEUTER']
moods = ['N/A', 'CONDITIONAL_MOOD', 'IMPERATIVE', 'INDICATIVE', 'INTERROGATIVE', 'JUSSIVE', 'SUBJUNCTIVE']
persons = ['N/A', 'FIRST', 'SECOND', 'THIRD', 'REFLEXIVE_PERSON']
reciprocities = ['N/A', 'RECIPROCAL', 'NON_RECIPROCAL']
tenses = ['N/A', 'CONDITIONAL_TENSE', 'FUTURE', 'PAST', 'PRESENT', 'IMPERFECT', 'PLUPERFECT']
voices = ['N/A', 'ACTIVE', 'CAUSATIVE', 'PASSIVE']
dependency_edges = ['N/A', 'ABBREV', 'ACOMP', 'ADVCL', 'ADVMOD', 'AMOD', 'APPOS', 'ATTR', 'AUX', 'AUXPASS', 'CC', 'CCOMP', 'CONJ', 'CSUBJ', 'CSUBJPASS', 'DEP', 'DET', 'DISCOURSE', 'DOBJ', 'EXPL', 'GOESWITH', 'IOBJ', 'MARK', 'MWE', 'MWV', 'NEG', 'NN', 'NPADVMOD', 'NSUBJ', 'NSUBJPASS', 'NUM', 'NUMBER', 'P', 'PARATAXIS', 'PARTMOD', 'PCOMP', 'POBJ', 'POSS', 'POSTNEG', 'PRECOMP', 'PRECONJ', 'PREDET', 'PREF', 'PREP', 'PRONL', 'PRT', 'PS', 'QUANTMOD', 'RCMOD', 'RCMODREL', 'RDROP', 'REF', 'REMNANT', 'REPARANDUM', 'ROOT', 'SNUM', 'SUFF', 'TMOD', 'TOPIC', 'VMOD', 'VOCATIVE', 'XCOMP', 'SUFFIX', 'TITLE', 'ADVPHMOD', 'AUXCAUS', 'AUXVV', 'DTMOD', 'FOREIGN', 'KW', 'LIST', 'NOMC', 'NOMCSUBJ', 'NOMCSUBJPASS', 'NUMC', 'COP', 'DISLOCATED', 'ASP', 'GMOD', 'GOBJ', 'INFMOD', 'MES', 'NCOMP']
entities_type = ["N/A", "PERSON", "LOCATION", "ORGANIZATION", "EVENT", "WORK_OF_ART", "CONSUMER_GOOD", "OTHER", "PHONE_NUMBER", "ADDRESS", "DATE", "NUMBER", "PRICE"]
mentions_type = ["N/A", "PROPER", "COMMON"]
'''

def translate_labels(language):
    translations = {
        'en': {
            'parts_of_speech': ['N/A', 'ADJ', 'ADP', 'ADV', 'CONJ', 'DET', 'NOUN', 'NUM', 'PRON', 'PRT', 'PUNCT', 'VERB', 'X', 'AFFIX'],
            'numbers': ['N/A', 'SINGULAR', 'PLURAL', 'DUAL'],
            'propers': ['N/A', 'PROPER', 'NOT_PROPER'],
            'aspects': ['N/A', 'PERFECTIVE', 'IMPERFECTIVE', 'PROGRESSIVE'],
            'cases': ['N/A', 'ACCUSATIVE', 'ADVERBIAL', 'COMPLEMENTIVE', 'DATIVE', 'GENITIVE', 'INSTRUMENTAL', 'LOCATIVE', 'NOMINATIVE', 'OBLIQUE', 'PARTITIVE', 'PREPOSITIONAL', 'REFLEXIVE_CASE', 'RELATIVE_CASE', 'VOCATIVE'],
            'forms': ['N/A', 'ADNOMIAL', 'AUXILIARY', 'COMPLEMENTIZER', 'FINAL_ENDING', 'GERUND', 'REALIS', 'IRREALIS', 'SHORT', 'LONG', 'ORDER', 'SPECIFIC'],
            'genders': ['N/A', 'FEMININE', 'MASCULINE', 'NEUTER'],
            'moods': ['N/A', 'CONDITIONAL_MOOD', 'IMPERATIVE', 'INDICATIVE', 'INTERROGATIVE', 'JUSSIVE', 'SUBJUNCTIVE'],
            'persons': ['N/A', 'FIRST', 'SECOND', 'THIRD', 'REFLEXIVE_PERSON'],
            'reciprocities': ['N/A', 'RECIPROCAL', 'NON_RECIPROCAL'],
            'tenses': ['N/A', 'CONDITIONAL_TENSE', 'FUTURE', 'PAST', 'PRESENT', 'IMPERFECT', 'PLUPERFECT'],
            'voices': ['N/A', 'ACTIVE', 'CAUSATIVE', 'PASSIVE'],
            'dependency_edges': ['N/A', 'ABBREV', 'ACOMP', 'ADVCL', 'ADVMOD', 'AMOD', 'APPOS', 'ATTR', 'AUX', 'AUXPASS', 'CC', 'CCOMP', 'CONJ', 'CSUBJ', 'CSUBJPASS', 'DEP', 'DET', 'DISCOURSE', 'DOBJ', 'EXPL', 'GOESWITH', 'IOBJ', 'MARK', 'MWE', 'MWV', 'NEG', 'NN', 'NPADVMOD', 'NSUBJ', 'NSUBJPASS', 'NUM', 'NUMBER', 'P', 'PARATAXIS', 'PARTMOD', 'PCOMP', 'POBJ', 'POSS', 'POSTNEG', 'PRECOMP', 'PRECONJ', 'PREDET', 'PREF', 'PREP', 'PRONL', 'PRT', 'PS', 'QUANTMOD', 'RCMOD', 'RCMODREL', 'RDROP', 'REF', 'REMNANT', 'REPARANDUM', 'ROOT', 'SNUM', 'SUFF', 'TMOD', 'TOPIC', 'VMOD', 'VOCATIVE', 'XCOMP', 'SUFFIX', 'TITLE', 'ADVPHMOD', 'AUXCAUS', 'AUXVV', 'DTMOD', 'FOREIGN', 'KW', 'LIST', 'NOMC', 'NOMCSUBJ', 'NOMCSUBJPASS', 'NUMC', 'COP', 'DISLOCATED', 'ASP', 'GMOD', 'GOBJ', 'INFMOD', 'MES', 'NCOMP'],
            'entities_type': ["N/A", "PERSON", "LOCATION", "ORGANIZATION", "EVENT", "WORK_OF_ART", "CONSUMER_GOOD", "OTHER", "PHONE_NUMBER", "ADDRESS", "DATE", "NUMBER", "PRICE"],
            'mentions_type': ["N/A", "PROPER", "COMMON"]
        },
        'fr': {
            'parts_of_speech': ['N/A', 'ADJ', 'ADP', 'ADV', 'CONJ', 'DET', 'NOUN', 'NUM', 'PRON', 'PRT', 'PUNCT', 'VERB', 'X', 'AFFIX'],
            'numbers': ['N/A', 'SINGULIER', 'PLURIEL', 'DUAL'],
            'propers': ['N/A', 'PROPRE', 'PAS_PROPRE'],
            'aspects': ['N/A', 'PERFECTIF', 'IMPARFAIT', 'PROGRESSIF'],
            'cases': ['N/A', 'ACCUSATIF', 'ADVERBIAL', 'COMPLÉMENT', 'DATIF', 'GÉNITIF', 'INSTRUMENTAL', 'LOCATIF', 'NOMINATIF', 'OBLIQUE', 'PARTITIF', 'PRÉPOSITIONNEL', 'CAS_RÉFLÉCHI', 'CAS_RELATIF', 'VOCATIF'],
            'forms': ['N/A', 'ADNOMIAL', 'AUXILIAIRE', 'COMPLÉMENTISATEUR', 'FINAL_ENDING', 'GÉRONDIF', 'RÉEL', 'IRRÉEL', 'COURT', 'LONG', 'ORDRE', 'SPÉCIFIQUE'],
            'genders': ['N/A', 'FÉMININ', 'MASCULIN', 'NEUTRE'],
            'moods': ['N/A', 'CONDITIONNEL', 'IMPERATIF', 'INDICATIF', 'INTERROGATIF', 'JUSSIF', 'SUBJONCTIF'],
            'persons': ['N/A', 'PREMIÈRE', 'DEUXIÈME', 'TROISIÈME', 'PERSONNE_RÉFLÉCHIE'],
            'reciprocities': ['N/A', 'RÉCIPROQUE', 'NON_RÉCIPROQUE'],
            'tenses': ['N/A', 'CONDITIONNEL', 'FUTUR', 'PASSÉ', 'PRÉSENT', 'IMPARFAIT', 'PLUS-QUE-PARFAIT'],
            'voices': ['N/A', 'ACTIF', 'CAUSATIF', 'PASSIF'],
            'dependency_edges': ['N/A', 'ABBRÉV', 'ACOMP', 'ADVCL', 'ADVMOD', 'AMOD', 'APPOS', 'ATTR', 'AUX', 'AUXPASS', 'CC', 'CCOMP', 'CONJ', 'CSUBJ', 'CSUBJPASS', 'DEP', 'DET', 'DISCOURS', 'DOBJ', 'EXPL', 'GOESWITH', 'IOBJ', 'MARK', 'MWE', 'MWV', 'NEG', 'NN', 'NPADVMOD', 'NSUBJ', 'NSUBJPASS', 'NUM', 'NUMBER', 'P', 'PARATAXIS', 'PARTMOD', 'PCOMP', 'POBJ', 'POSS', 'POSTNEG', 'PRECOMP', 'PRECONJ', 'PREDET', 'PREF', 'PREP', 'PRONL', 'PRT', 'PS', 'QUANTMOD', 'RCMOD', 'RCMODREL', 'RDROP', 'REF', 'REMNANT', 'REPARANDUM', 'ROOT', 'SNUM', 'SUFF', 'TMOD', 'TOPIC', 'VMOD', 'VOCATIF', 'XCOMP', 'SUFFIXE', 'TITRE', 'ADVPHMOD', 'AUXCAUS', 'AUXVV', 'DTMOD', 'ÉTRANGER', 'KW', 'LISTE', 'NOMC', 'NOMCSUBJ', 'NOMCSUBJPASS', 'NUMC', 'COP', 'DISLOQUÉ', 'ASP', 'GMOD', 'GOBJ', 'INFMOD', 'MES', 'NCOMP'],
            'entities_type': ["N/A", "PERSONNE", "EMPLACEMENT", "ORGANISATION", "ÉVÉNEMENT", "ŒUVRE_D'ART", "BIEN_DE_CONSOMMATION", "AUTRE", "NUMÉRO_DE_TÉLÉPHONE", "ADRESSE", "DATE", "NUMÉRO", "PRIX"],
            'mentions_type': ["N/A", "PROPRE", "COMMUN"]
        },
    }

    return translations.get(language, translations['en'])



# PARTS OF SPEECH TRANSLATIONS
'''
0 UNKNOWN Unknown
1 ADJ Adjective
2 ADP Adposition (preposition and postposition)
3 ADV Adverb
4 CONJ  Conjunction
5 DET Determiner
6 NOUN  Noun (common and proper)
7 NUM Cardinal number
8 PRON  Pronoun
9 PRT Particle or other function word
10 PUNCT  Punctuation
11 VERB Verb (all tenses and modes)
12 X  Other: foreign words, typos, abbreviations
13 AFFIX  Affix
'''

# NUMBER TRANSLATIONS
''' NUMBER Count distinctions.
0 NUMBER_UNKNOWN  Number is not applicable in the analyzed language or is not predicted.
1 SINGULAR  Singular
2 PLURAL  Plural
3 DUAL  Dual
'''

# PROPER TRANSLATIONS
''' PROPER This category shows if the token is part of a proper name.
0 PROPER_UNKNOWN  Proper is not applicable in the analyzed language or is not predicted.
1 PROPER  Proper
2 NOT_PROPER  Not proper
'''

# ASPECT TRANSLATIONS
''' ASPECT The characteristic of a verb that expresses time flow during an event.
0 ASPECT_UNKNOWN  Aspect is not applicable in the analyzed language or is not predicted.
1 PERFECTIVE  Perfective
2 IMPERFECTIVE  Imperfective
3 PROGRESSIVE Progressive
'''

# CASE TRANSLATIONS
''' CASE The grammatical function performed by a noun or pronoun in a phrase, clause, or sentence. In some languages, other parts of speech, such as adjective and determiner, take case inflection in agreement with the noun.
0 CASE_UNKNOWN  Case is not applicable in the analyzed language or is not predicted.
1 ACCUSATIVE  Accusative
2 ADVERBIAL Adverbial
3 COMPLEMENTIVE Complementive
4 DATIVE  Dative
5 GENITIVE  Genitive
6 INSTRUMENTAL  Instrumental
7 LOCATIVE  Locative
8 NOMINATIVE  Nominative
9 OBLIQUE Oblique
10 PARTITIVE  Partitive
11 PREPOSITIONAL  Prepositional
12 REFLEXIVE_CASE Reflexive
13 RELATIVE_CASE  Relative
14 VOCATIVE Vocative
'''

# FORM TRANSLATIONS
''' FORM Depending on the language, Form can be categorizing different forms of verbs, adjectives, adverbs, etc. For example, categorizing inflected endings of verbs and adjectives or distinguishing between short and long forms of adjectives and participles
0 FORM_UNKNOWN  Form is not applicable in the analyzed language or is not predicted.
1 ADNOMIAL  Adnomial
2 AUXILIARY Auxiliary
3 COMPLEMENTIZER  Complementizer
4 FINAL_ENDING  Final ending
5 GERUND  Gerund
6 REALIS  Realis
7 IRREALIS  Irrealis
8 SHORT Short form
9 LONG  Long form
10 ORDER  Order form
11 SPECIFIC Specific form
'''

# GENDER TRANSLATIONS
''' GENDER Gender classes of nouns reflected in the behaviour of associated words.
0 GENDER_UNKNOWN  Gender is not applicable in the analyzed language or is not predicted.
1 FEMININE  Feminine
2 MASCULINE Masculine
3 NEUTER  Neuter
'''

# MOOD TRANSLATIONS
''' MOOD The grammatical feature of verbs, used for showing modality and attitude.
0 MOOD_UNKNOWN  Mood is not applicable in the analyzed language or is not predicted.
1 CONDITIONAL_MOOD  Conditional
2 IMPERATIVE  Imperative
3 INDICATIVE  Indicative
4 INTERROGATIVE Interrogative
5 JUSSIVE Jussive
6 SUBJUNCTIVE Subjunctive
'''

# PERSON TRANSLATIONS
''' PERSON The distinction between the speaker, second person, third person, etc.
0 PERSON_UNKNOWN  Person is not applicable in the analyzed language or is not predicted.
1 FIRST First
2 SECOND  Second
3 THIRD Third
4 REFLEXIVE_PERSON  Reflexive
'''

# RECIPROCITY TRANSLATIONS
''' RECIPROCITY Reciprocal features of a pronoun.
0 RECIPROCITY_UNKNOWN Reciprocity is not applicable in the analyzed language or is not predicted.
1 RECIPROCAL  Reciprocal
2 NON_RECIPROCAL  Non-reciprocal
'''

# TENSE TRANSLATIONS
''' TENSE Time reference.
0 TENSE_UNKNOWN Tense is not applicable in the analyzed language or is not predicted.
1 CONDITIONAL_TENSE Conditional
2 FUTURE  Future
3 PAST  Past
4 PRESENT Present
5 IMPERFECT Imperfect
6 PLUPERFECT  Pluperfect
'''

# VOICE TRANSLATIONS
''' VOICE The relationship between the action that a verb expresses and the participants identified by its arguments.
0 VOICE_UNKNOWN Voice is not applicable in the analyzed language or is not predicted.
1 ACTIVE  Active
2 CAUSATIVE Causative
3 PASSIVE Passive
'''

# DEPENDENCY EDGE TRANSLATIONS
''' LABEL The parse label enum for the token.
0 UNKNOWN Unknown
1 ABBREV  Abbreviation modifier
2 ACOMP Adjectival complement
3 ADVCL Adverbial clause modifier
4 ADVMOD  Adverbial modifier
5 AMOD  Adjectival modifier of an NP
6 APPOS Appositional modifier of an NP
7 ATTR  Attribute dependent of a copular verb
8 AUX Auxiliary (non-main) verb
9 AUXPASS Passive auxiliary
10 CC Coordinating conjunction
11 CCOMP  Clausal complement of a verb or adjective
12 CONJ Conjunct
13 CSUBJ  Clausal subject
14 CSUBJPASS  Clausal passive subject
15 DEP  Dependency (unable to determine)
16 DET  Determiner
17 DISCOURSE  Discourse
18 DOBJ Direct object
19 EXPL Expletive
20 GOESWITH Goes with (part of a word in a text not well edited)
21 IOBJ Indirect object
22 MARK Marker (word introducing a subordinate clause)
23 MWE  Multi-word expression
24 MWV  Multi-word verbal expression
25 NEG  Negation modifier
26 NN Noun compound modifier
27 NPADVMOD Noun phrase used as an adverbial modifier
28 NSUBJ  Nominal subject
29 NSUBJPASS  Passive nominal subject
30 NUM  Numeric modifier of a noun
31 NUMBER Element of compound number
32 P  Punctuation mark
33 PARATAXIS  Parataxis relation
34 PARTMOD  Participial modifier
35 PCOMP  The complement of a preposition is a clause
36 POBJ Object of a preposition
37 POSS Possession modifier
38 POSTNEG  Postverbal negative particle
39 PRECOMP  Predicate complement
40 PRECONJ  Preconjunt
41 PREDET Predeterminer
42 PREF Prefix
43 PREP Prepositional modifier
44 PRONL  The relationship between a verb and verbal morpheme
45 PRT  Particle
46 PS Associative or possessive marker
47 QUANTMOD Quantifier phrase modifier
48 RCMOD  Relative clause modifier
49 RCMODREL Complementizer in relative clause
50 RDROP  Ellipsis without a preceding predicate
60 REF  Referent
61 REMNANT  Remnant
62 REPARANDUM Reparandum
63 ROOT Root
64 SNUM Suffix specifying a unit of number
65 SUFF Suffix
66 TMOD Temporal modifier
67 TOPIC  Topic marker
68 VMOD Clause headed by an infinite form of the verb that modifies a noun
69 VOCATIVE Vocative
70 XCOMP  Open clausal complement
71 SUFFIX Name suffix
72 TITLE  Name title
73 ADVPHMOD Adverbial phrase modifier
74 AUXCAUS  Causative auxiliary
75 AUXVV  Helper auxiliary
76 DTMOD  Rentaishi (Prenominal modifier)
77 FOREIGN  Foreign words
78 KW Keyword
79 LIST List for chains of comparable items
70 NOMC Nominalized clause
71 NOMCSUBJ Nominalized clausal subject
72 NOMCSUBJPASS Nominalized clausal passive
73 NUMC Compound of numeric modifier
74 COP  Copula
75 DISLOCATED Dislocated relation (for fronted/topicalized elements)
76 ASP  Aspect marker
77 GMOD Genitive modifier
78 GOBJ Genitive object
79 INFMOD Infinitival modifier
81 MES  Measure
82 NCOMP  Nominal complement of a noun
'''

# ENTITY TYPE TRANSLATIONS
''' TYPE The type of the entity. For most entity types, the associated metadata is a Wikipedia URL (wikipedia_url) and Knowledge Graph MID (mid). The table below lists the associated fields for entities that have different metadata.
0 UNKNOWN Unknown
1 PERSON  Person
2 LOCATION  Location
3 ORGANIZATION  Organization
4 EVENT Event
5 WORK_OF_ART Artwork
6 CONSUMER_GOOD Consumer product
7 OTHER Other types of entities
8 PHONE_NUMBER  Phone number
        The metadata lists the phone number, formatted according to local convention, plus whichever additional elements appear in the text:
        number - the actual number, broken down into sections as per local convention
        national_prefix - country code, if detected
        area_code - region or area code, if detected
        extension - phone extension (to be dialed after connection), if detected
9 ADDRESS Address
      The metadata identifies the street number and locality plus whichever additional elements appear in the text:
      street_number - street number
      locality - city or town
      street_name - street/route name, if detected
      postal_code - postal code, if detected
      country - country, if detected<
      broad_region - administrative area, such as the state, if detected
      narrow_region - smaller administrative area, such as county, if detected
      sublocality - used in Asian addresses to demark a district within a city, if detected
10 DATE Date
    The metadata identifies the components of the date:
    year - four digit year, if detected
    month - two digit month number, if detected
    day - two digit day number, if detected
11 NUMBER Number
      The metadata is the number itself.

12 PRICE  Price
      The metadata identifies the value and currency.
'''

# MENTIONS TYPE TRANSLATIONS
'''
0 TYPE_UNKNOWN  Unknown
1 PROPER  Proper name
2 COMMON  Common noun (or noun compound)
'''


def sample_annotate_text(project_name, selected_text_ids, db_path):
    try:
        print(f"[INFO] Starting annotation process for project: {project_name}")

        google_nlp_key_path = None
        if g.current_user:
            google_nlp_key_path = g.current_user.get('google_nlp_key_path')
        
        if not google_nlp_key_path:
            print("[ERROR] Google NLP key path not found for current user or in app config.")
            return

        service_account_file = google_nlp_key_path
        if not os.path.exists(service_account_file):
            print(f"[ERROR] Service account file not found at: {service_account_file}")
            return

        # Initialize Google NLP Client with the service account
        client = language_v1.LanguageServiceClient.from_service_account_file(service_account_file)

        # Load text pairs
        text_pairs = load_text_data(project_name, current_app.config['DATABASE_PATH'])
        print(f"[INFO] Loaded {len(text_pairs)} text pairs for project: {project_name}")

        # Filter selected texts
        selected_texts = [pair for pair in text_pairs if str(pair['id']) in selected_text_ids]
        if not selected_texts:
            print(f"[WARNING] No matching text IDs found for project: {project_name}")
            return

        # Process each selected text pair
        for pair in selected_texts:
            pair_id = pair['id']
            error_text = pair.get('error_text')
            corrected_text = pair.get('corrected_text')

            print(f"[INFO] Processing text pair ID: {pair_id}")

            # Process and save error and corrected text
            try:
                print(f"[INFO] Processing error text for ID: {pair_id}")
                process_and_save_text(project_name, client, pair_id, 'error_text', error_text)

                print(f"[INFO] Processing corrected text for ID: {pair_id}")
                process_and_save_text(project_name, client, pair_id, 'corrected_text', corrected_text)
            except Exception as e:
                print(f"[ERROR] Error processing texts for ID {pair_id}: {e}")
                continue

            # Get genre and main idea
            try:
                genre, main_idea = get_genre_and_main_idea(project_name, corrected_text)
                print(f"[INFO] Genre for ID {pair_id}: {genre}")
                print(f"[INFO] Main idea for ID {pair_id}: {main_idea}")

                # Save genre and main idea to the database
                save_genre_and_main_idea(project_name, genre, main_idea, pair_id, current_app.config['DATABASE_PATH'])
                print(f"[INFO] Saved genre and main idea for ID: {pair_id}")
            except Exception as e:
                print(f"[ERROR] Error analyzing text for ID {pair_id}: {e}")

        # Update project states
        update_nlp_state(project_name, db_path)
        print(f"[INFO] NLP state updated for project: {project_name}")

        update_genre_state(project_name, db_path)
        print(f"[INFO] Genre state updated for project: {project_name}")

        print(f"[INFO] Annotation process completed successfully for project: {project_name}")

    except Exception as e:
        print(f"[CRITICAL] Critical error in sample_annotate_text: {e}")


def process_and_save_text(project_name, client, pair_id, text_type, text_content):
    file_name, nlp_active, language, genre_active = get_project_file(project_name, current_app.config['DATABASE_PATH'])

    translations = translate_labels(language)
    parts_of_speech = translations['parts_of_speech']
    numbers = translations['numbers']
    propers = translations['propers']
    aspects = translations['aspects']
    cases = translations['cases']
    forms = translations['forms']
    genders = translations['genders']
    moods = translations['moods']
    persons = translations['persons']
    reciprocities = translations['reciprocities']
    tenses = translations['tenses']
    voices = translations['voices']
    dependency_edges = translations['dependency_edges']
    entities_type = translations['entities_type']
    mentions_type = translations['mentions_type']

    print(f"Processing text for pair ID {pair_id} and text type {text_type}")
    type_ = language_v1.Document.Type.PLAIN_TEXT
    encoding_type = language_v1.EncodingType.UTF8

    document = {"content": text_content, "type_": type_, "language": language}
    features = {"extract_syntax": True, "extract_entities": True}

    response = client.annotate_text(request={'document': document, 'features': features, 'encoding_type': encoding_type})
    json_response = json.loads(type(response).to_json(response))

    def safe_get(arr, idx, fallback='N/A'):
        try:
            return arr[idx]
        except Exception:
            return fallback

    tokens = []
    for token in json_response['tokens']:
        token_content = token['text']['content']
        position = token['text']['beginOffset']
        # Raw enum codes from API
        tag_code = token['partOfSpeech']['tag']
        number_code = token['partOfSpeech']['number']
        proper_code = token['partOfSpeech']['proper']
        aspect_code = token['partOfSpeech']['aspect']
        case_code = token['partOfSpeech']['case']
        form_code = token['partOfSpeech']['form']
        gender_code = token['partOfSpeech']['gender']
        mood_code = token['partOfSpeech']['mood']
        person_code = token['partOfSpeech']['person']
        reciprocity_code = token['partOfSpeech']['reciprocity']
        tense_code = token['partOfSpeech']['tense']
        voice_code = token['partOfSpeech']['voice']
        head_token = token['dependencyEdge']['headTokenIndex']
        dep_label_code = token['dependencyEdge']['label']

        # Labels mapped to project language
        tag = safe_get(parts_of_speech, tag_code)
        number = safe_get(numbers, number_code)
        proper = safe_get(propers, proper_code)
        aspect = safe_get(aspects, aspect_code)
        case = safe_get(cases, case_code)
        form = safe_get(forms, form_code)
        gender = safe_get(genders, gender_code)
        mood = safe_get(moods, mood_code)
        person = safe_get(persons, person_code)
        reciprocity = safe_get(reciprocities, reciprocity_code)
        tense = safe_get(tenses, tense_code)
        voice = safe_get(voices, voice_code)
        label = safe_get(dependency_edges, dep_label_code)
        lemma = token['lemma']

        tokens.append({
            'pair_id': pair_id,
            'text_type': text_type,
            'token': token_content,
            'position': position,
            'tag': tag,
            'number': number,
            'proper': proper,
            'aspect': aspect,
            'case': case,
            'form': form,
            'gender': gender,
            'mood': mood,
            'person': person,
            'reciprocity': reciprocity,
            'tense': tense,
            'voice': voice,
            'head_token': head_token,
            'label': label,
            'lemma': lemma,
            'tag_code': tag_code,
            'number_code': number_code,
            'proper_code': proper_code,
            'aspect_code': aspect_code,
            'case_code': case_code,
            'form_code': form_code,
            'gender_code': gender_code,
            'mood_code': mood_code,
            'person_code': person_code,
            'reciprocity_code': reciprocity_code,
            'tense_code': tense_code,
            'voice_code': voice_code,
            'dep_label_code': dep_label_code,
        })

    print(f"Saving {len(tokens)} tokens for pair ID {pair_id} and text type {text_type}")
    save_google_nlp_to_database(project_name, 'tokens', tokens, current_app.config['DATABASE_PATH'])

    entities = []
    for entity in json_response['entities']:
        entity_name = entity['name']
        entity_type_code = entity['type']
        entity_type = safe_get(entities_type, entity_type_code)
        entity_content = entity['mentions'][0]['text']['content']
        entity_position = entity['mentions'][0]['text']['beginOffset']
        mention_type_code = entity['mentions'][0]['type']
        entity_cop = safe_get(mentions_type, mention_type_code)

        entities.append({
            'pair_id': pair_id,
            'text_type': text_type,
            'name': entity_name,
            'type': entity_type,
            'content': entity_content,
            'position': entity_position,
            'common_or_proper': entity_cop,
            'entity_type_code': entity_type_code,
            'mention_type_code': mention_type_code,
        })

    print(f"Saving {len(entities)} entities for pair ID {pair_id} and text type {text_type}")
    save_google_nlp_to_database(project_name, 'entities', entities, current_app.config['DATABASE_PATH'])

    classifications = classify_text(project_name, client, text_content, pair_id, 'corrected_text')
    print(f"Saving {len(classifications)} classifications for pair ID {pair_id} and text type corrected_text")
    save_google_nlp_to_database(project_name, 'classifications', classifications, current_app.config['DATABASE_PATH'])

def classify_text(project_name, client, text_content, pair_id, text_type):
    type_ = language_v1.Document.Type.PLAIN_TEXT

    # Retrieve the language
    file_name, nlp_active, language, genre_active = get_project_file(project_name, current_app.config['DATABASE_PATH'])

    document = {"content": text_content, "type_": type_, "language": language}
    content_categories_version = (
        language_v1.ClassificationModelOptions.V2Model.ContentCategoriesVersion.V2
    )

    response = client.classify_text(
        request={
            "document": document,
            "classification_model_options": {
                "v2_model": {"content_categories_version": content_categories_version}
            },
        }
    )

    classifications = []
    for category in response.categories:
        category_name = category.name
        confidence = category.confidence
        classifications.append({
            'pair_id': pair_id,
            'text_type': text_type,
            'category_name': category_name,
            'confidence': confidence,
        })

    return classifications
