import configparser
import csv
import logging
import os
import re
import sys

class NoteMapper:
    def __init__(self):
        dir_path = os.path.dirname(os.path.realpath(__file__))
        filename = 'janne-v3-numeric-sounds-unique-id.csv'
        filename = os.path.join(dir_path, filename)
        # filename is in the same directory as the script
        # read the file and create a mapping
        self.mapping = {}
        with open(filename, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                id = int(row['id'])
                if id >= 0:
                    self.mapping[id] = row

    def map(self, id):
        return self.mapping.get(id, None)

class Note:
    # [P2]
    # type = 1649545214
    # distance = 0.00001
    # flag = 0

    flags = {
        "None": 0x00,
        "Narrows": 0x01,
        "WideOut": 0x02,
        "Tightens": 0x04,
        "x1": 0x08,
        "x2": 0x10,
        "DontCut": 0x20,
        "Cut": 0x40,
        "TightensBad": 0x80,
        "x3": 0x0100,
        "x4": 0x0100,
        "x5": 0x0200,
        "Long": 0x0400,
        "x6": 0x0800,
        "x7": 0x1000,
        "Maybe": 0x2000,
        "x9": 0x4000,
        "x10": 0x8000,
        "x11": 0x00010000,
        "x12": 0x00020000,
        "x13": 0x00040000,
        "x14": 0x00080000,
        "x15": 0x00100000,
        "x16": 0x00200000,
        "x17": 0x00400000,
        "x19": 0x00800000,
        "x20": 0x01000000,
        "x21": 0x02000000,
        "x22": 0x04000000,
        "x23": 0x08000000,
        "x24": 0x10000000,
        "x25": 0x20000000,
        "x26": 0x40000000,
        "x27": 0x80000000,
    }

    # Define only the explicitly named flags
    named_flags = {
        "None": 0x00,
        "Narrows": 0x01,
        "WideOut": 0x02,
        "Tightens": 0x04,
        "DontCut": 0x20,
        "Cut": 0x40,
        "TightensBad": 0x80,
        "Long": 0x0400,
        "Maybe": 0x2000,
    }

    def __init__(self, type, distance, flag):
        self.type = type
        self.distance = distance
        self.flag = flag
        self.flags = self.parse_flag(flag)

    def __str__(self) -> str:
        return f"Type: {self.type}, Distance: {self.distance}, Flag: {self.flag}, Flags: {self.flags}"

    def parse_flag(self, flag_value):
        # Parse the flags
        set_flags = {name for name, value in self.flags.items() if flag_value & value}
        named_set_flags = {name for name, value in self.named_flags.items() if flag_value & value}

        return set_flags

    def print_flags_in_binary(self):
        for name, value in self.flags.items():
            print(f"{name}: {format(value, 'b')}")



    # def parse_flag(self, flag):
    #     # flag is a bitfield
    #     # get all bits up to 16384
    #     flags = set()
    #     for i in range(15):
    #         if flag & (1 << i):
    #             flags.add(1 << i)
    #     return flags


class Roadbook:
    def __init__(self, filename):
        self.notes = {}
        self.read_ini(filename)

    def read_ini(self, filename):
        config = configparser.ConfigParser(strict=False)
        encoding = 'utf-8'
        encoding = 'cp1252'
        logging.info(f"Reading {filename}")
        try:
            config.read(filename, encoding=encoding)
        except Exception as e:
            logging.error(f'Error reading {filename}: {e}')
            # work around for configparser not handling utf-8
            with open(filename, 'r', encoding=encoding) as f:
                content = f.read()
            # remove the BOM
            content = content.replace('\ufeff', '')
            config.read_string(content)

        for section in config.sections():
            if section == 'PACENOTES':
                self.num_notes = config.getint(section, 'count')
                continue

            if section.startswith('P'):
                note = Note(config.getint(section, 'type'),
                            config.getfloat(section, 'distance'),
                            config.getint(section, 'flag'))

                # the high notes are not interesting
                if note.type > 6_000_000:
                    continue

                if note.flag > 65_000:
                    note.flag = 0

                note_id = int(section[1:])
                self.notes[note_id] = note

    def get_notes(self, note_type):
        notes = []
        for note_id, note in self.notes.items():
            if note.type == note_type:
                notes.append(note)
        return notes

    def get_notes_flag(self, note_flag):
        notes = []
        for note_id, note in self.notes.items():
            if note.flag == note_flag:
                notes.append(note)
        return notes

    def note_types(self):
        types = set()
        for note in self.notes.values():
            types.add(note.type)
        return types

    def note_flags(self):
        flags = set()
        for note in self.notes.values():
            flags |= note.flags
        return flags

class Roadbooks:
    def __init__(self, path):
        self.base_path = path
        self.books = {}

    def read_roadbooks(self, name):
        # recurse into self.base_path
        logging.info(f"Analyzing {name}")
        if name.startswith('/'):
            # name is a regex
            regex = name.lstrip('/')
            regex = regex.rstrip('/')
            name = re.compile(regex)
        for root, dirs, files in os.walk(self.base_path):
            for file in files:
                if name == file or (isinstance(name, re.Pattern) and name.match(file)):
                    if file.endswith('.ini'):
                        self.read_roadbook(file, os.path.join(root, file))

    def read_roadbook(self, name, filename):
        book = Roadbook(filename)
        self.books[name] = book

    def analyze_books(self):
        # get all note types
        note_types = set()
        note_flags = set()
        for book in self.books.values():
            note_types |= book.note_types()
            note_flags |= book.note_flags()

        row = ['name']
        note_types_list = sorted(list(note_types))
        note_flags_list = sorted(list(note_flags))
        row.extend(note_types_list)
        # prepend 'flag_' to note_flags
        note_flags_list = [f'flag_{x}' for x in note_flags_list]
        row.extend(note_flags_list)

        csv_writer = csv.writer(sys.stdout)
        csv_writer.writerow(row)

        books = self.books.items()
        # sort by name
        books = sorted(books, key=lambda x: x[0])
        for name, book in books:
            row = []
            row.append(name)
            for note_type in note_types_list:
                book_note_types = book.get_notes(note_type)
                row.append(len(book_note_types))
            for note_flag in note_flags_list:
                note_flag_id = int(note_flag[5:])
                book_note_flags = book.get_notes_flag(note_flag_id)
                row.append(len(book_note_flags))
            csv_writer.writerow(row)


    def csv_output(self, name, notes):
        note_types = sorted(notes.keys())
        for note_type in note_types:
            note_list = notes[note_type]
            print(f"{note_type}: {len(note_list)}")



if __name__ == "__main__":
    book = Roadbook("Luppis Pacenote Pack V2 [26.1.2024]/ALL PACENOTES/PACENOTE WITH FOLDER STRUCTURE/Plugins/NGPCarMenu/MyPacenotes/Ahvenus I BTB/Ahvenus I_default.ini")

    print(book.num_notes)
    print(book.note_types())
