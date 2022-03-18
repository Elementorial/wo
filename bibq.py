import sys, re, pandas as pd #, json, doctest, pytest,
import meta
from os.path import exists

def destructure_match(match):
    return match[3], match[4], match[6], match[7], match[9]

# Remove previously generated reference tags and regenerate them.
def handle_references(line_index, line, lines, df):
    # Ungenerate generated in-line references
    # Grouping (parentheses) around the full regular expression is necessary for the splits to include what the pattern matches.
    splits = re.split(r'(<r r="(?<=<r r=")[^>]*(?!<)[^<]*<\/r>)', line) # Split the line based on generated tags.
    # For each reference, remove the generated quotation and closing tag.
    for split_index, split in enumerate(splits): # For every split, whether it's a match or a non-match.
        matches = re.search(r'<r r="(?<=<r r=")[^>]*(?!<)[^<]*<\/r>', split) # Search for the reference to be generated.
        if not matches: continue # Skip this split if it's not a split that contains a reference.
        matches = re.search(r'(<r r="(?<=<r r=")[^>]*)(?!<)[^<]*<\/r>', matches[0]) # Select into the first regex group only the reference which is to be generated.
        splits[split_index] = f'{matches[1]}>' # Set this split index, which was a generated reference, to be only the section representing the ungenerated reference.
    lines[line_index] = ''.join(splits) # Rejoin the splits into the line, with the generated referenced now ungenerated.
    
    # Generate or regenerate in-line references
    # Create a list of the splits in the line; splits are done for each reference to isolate them.
    splits = re.split(r'(<r r="[^>\n]*">)', lines[line_index]) # Use indexed var on `lines` since `line` has not been modified at this point.
    for split_index, split in enumerate(splits):
        # For the splits that matched the pattern, find all the references within the attribute field of the html tag.
        if not re.search(r'(<r r="[^>\n]*">)', split): # Skip this line if it's not a reference to avoid mismatches.
            continue
        matches = re.findall(r'(<r r="|\s)((\s?|\s?([1-3])\s?)(([A-Za-z]|\s)+)\s(\d+)\s(\d+)(\s(\d+))?)(,|">)', split)
        for match_index, match in enumerate(matches):
            verse_text = build_verse_text(match, line_index, df)
            # Append closing tag to the split if it's for the last verse.
            last_match = match_index == len(matches) - 1
            if last_match: verse_text= f'{verse_text}</r>'
            # Add 2 spaces to separate separate quotations on the same line.
            splits[split_index] += f'{verse_text}; ' if not last_match else f'{verse_text}'
    # Join the modified splits back into one line, now with scriptures quoted.
    lines[line_index] = ''.join(splits)

def handle_citations(line_index, line, lines, citation_verses, df):
    splits = re.split(r'(<r c="(?<=<r c=")[^>]*(?!<)[^<]*<\/r>)', line)
    for split_index, split in enumerate(splits):
        matches = re.search(r'<r c="(?<=<r c=")[^>]*(?!<)[^<]*<\/r>', split)
        if not matches: continue
        matches = re.search(r'(<r c="(?<=<r c=")[^>]*)(?!<)[^<]*<\/r>', matches[0])
        splits[split_index] = f'{matches[1]}>'
    lines[line_index] = ''.join(splits) 
    
    splits = re.split(r'(<r c="[^>\n]*">)', lines[line_index])
    for split_index, split in enumerate(splits):
        if not re.search(r'(<r c="[^>\n]*">)', split): continue
        matches = re.findall(r'(<r c="|\s)((\s?|\s?([1-3])\s?)(([A-Za-z]|\s)+)\s(\d+)\s(\d+)(\s(\d+))?)(,|">)', split)

        for match_index, match in enumerate(matches):
            verse_citation = build_bible_citation(match, line_index)
            first_match = match_index == 0
            last_match = match_index == len(matches) - 1
            # Add c tag for multi-passage custom spacing since spacing isn't working due to either the csl file or quarto itself.
            if len(matches) == 1:
                splits[split_index] += f'@{verse_citation}</r>'
            else:
                if first_match: 
                    splits[split_index] += f'[@{verse_citation}; '
                elif last_match:
                    splits[split_index] += f'@{verse_citation}]</r>'
                else:
                    splits[split_index] += f'@{verse_citation}; '
            
            verse_text = build_verse_text(match, line_index, df)
            citation_verses.update({verse_citation: verse_text})
    # Join the modified splits back into one line, now with quarto citation generated
    lines[line_index] = ''.join(splits)

def build_verse_text(match, line_index, df):
    book_number, book_name, chapter_number, starting_verse, ending_verse = destructure_match(match)
    # Check the abbreviation list if the book doesn't have a match.
    book = check_book(book_number, book_name, line_index)
    
    # Build the query based on the reference information.
    csv_book_index = meta.book_list.index(book) + 1
    # Query for the book, chapter, and verse or range of verses.
    verse_query = f'verse >= {starting_verse} and verse <= {ending_verse}' if ending_verse else f'verse == {starting_verse}'
    query_string = f'book == {csv_book_index} and chapter == {chapter_number} and {verse_query}'
    # Build the quotation data.
    accumulator = ''
    for result in df.query(query_string).itertuples():
        accumulator += f'{result.text} '
    # Add the verse or range of verses to its accumulator, and add the citation text.
    ending_format = f"-{ending_verse}" if ending_verse else ""
    accumulator = accumulator.strip()
    return f'{accumulator} ({book} {chapter_number}:{starting_verse}{ending_format})'

def build_bible_citation(match, line_index):
    book_number, book_name, chapter_number, starting_verse, ending_verse = destructure_match(match)
    # Check the abbreviation list if the book doesn't have a match.
    book = check_book(book_number, book_name, line_index)
    
    # Add the verse or range of verses to its accumulator, and add the citation text.
    ending_format = f"-{ending_verse}" if ending_verse else ""
    citation = f'{book} {chapter_number}:{starting_verse}{ending_format}'
    return citation.replace(' ','_')
     
def check_book(book_number, book_name, line_index):
    book = ' '.join((book_number, book_name)).strip() # Join the book number and name with a space, and strip spaces in case the book number is empty.
    if book.title() not in meta.book_list:
        try:
            book = meta.abbreviations[book.lower()]
        except KeyError:
            print(f'The book "{book}" was not found in the abbreviation list at line index {line_index}.')
            exit()
        except Exception as e:
            print(e)
            exit()
    return book.title()

# def remove_footnotes(line_index, line, lines):
#     # If this line is a generated footnote.
#     if re.match(r'^\[\^((\s?|\s?([1-3])\s?)(([A-Za-z]|\s)+)\s(\d+)\s(\d+)(\s(\d+))?)\]:.*$', lines[line_index]):
#         # Remove this line from `lines`, and the one before it since footnotes require a blank line above them.
#         lines[line_index-1:len(lines)] = lines[line_index+1:len(lines)] # Use the rest of the lines after this line to replace the generated quotation, the blank line before it, and the rest of the lines after this line.
#         return line_index-1
#     return line_index
#
# def generate_footnotes(line_index, line, lines):
#     # Split the line based on footnote citation syntax.
#     splits = re.split(r'(\[\^[^\]]*\]+?(?!:))', lines[line_index])
#     # Iterate backwards through each footnote citation on the line to order them properly, since they're inserted one at a time below the current line.
#     for split_index, split in reversed(list(enumerate(splits))): # For every split,
#         if not re.search(r'\[\^[^\]]*\]+?(?!:)', split): continue
#         matches = re.findall(rj'(\[\^|\s)((\s?|\s?([1-3])\s?)(([A-Za-z]|\s)+)\s(\d+)\s(\d+)(\s(\d+))?)(,|\])', split) # if the split is a reference,
#         for match_index, match in reversed(list(enumerate(matches))): # generate the footnotes below the line that has footnote citations to generate footnotes for.
#             verse_text = build_verse_text(match, line_index)
#             footnote_reference = match[1]
#             footnote_text = f'[^{footnote_reference}]: {verse_text}\n'
#             lines.insert(line_index+1, footnote_text)
#             lines.insert(line_index+1, '\n')

def replace_tabs_with_emsp(line_index, line, lines):
    lines[line_index] = re.sub('^>>', '&emsp;', lines[line_index])

def main():
    # csv_file = r'C:\Users\R\WorldviewOutreach\kjv.csv' if sys.platform == 'win32' else "/home/r/WorldviewOutreach/kjv.csv"
    csv_file = r'C:\Users\R\WorldviewOutreach\web.csv' if sys.platform == 'win32' else "/home/r/WorldviewOutreach/web.csv"
    transform_file = sys.argv[1] # Get the file name which should have been passed to this script.

    if sys.platform == 'win32':
        directory_character = '\\'
    else:
        directory_character = r'/'
    last_slash_index = transform_file.rfind(directory_character)+len(directory_character)
    file_directory = f'{transform_file[0:last_slash_index]}'

    sources_file = f'{file_directory}sources.bib'
    merged_file = f'{file_directory}merged.bib'

    citation_verses = {}
    with (
        open(transform_file, 'r', encoding='utf-8') as current_file,
        open(csv_file, 'r', encoding='utf-8') as bible_csv
    ):
        df = pd.read_csv(bible_csv)
        lines = current_file.readlines()

        # # Custom iterator since remove_footnotes modifies the loop index.
        # line_index = 0
        # while True:
        #     line = lines[line_index]
        #     line_index = remove_footnotes(line_index, line, lines)
        #     try:
        #         line_index = line_index + 1
        #         line = lines[line_index]
        #     except IndexError as e:
        #         break
        #     except Exception as e:
        #         print(e)
        #         exit()

        # Regular loop to modify the entire document, one line at a time, when possible.
        for line_index, line in enumerate(lines):
            handle_references(line_index, line, lines, df)
            line = lines[line_index] # Assign line to be the modified line, so that the next method has the modified line
            handle_citations(line_index, line, lines, citation_verses, df)
            # generate_footnotes(line_index, line, lines)
            replace_tabs_with_emsp(line_index, line, lines)

    # for line in lines: print(repr(line), end='') # Debugging print to view the entire document without writing to file.

    if not exists(sources_file):
        file = open(sources_file, 'x', encoding='utf-8')
        file.close()
    
    # Remove snapshot file references in the sources file.
    # One can't use r & w mode through two open commands for the same file and expect it to work in the same 'with' block.
    with open(sources_file, 'r', encoding = 'utf-8') as sources_in:
        content = sources_in.read()
        new_content = re.sub(r'\s*\bfile\s*=\s*\{[^}]*\},?', '', content)
    with open(sources_file, 'w', encoding = 'utf-8') as sources_out:
        sources_out.write(new_content)

    with (
        open(transform_file, 'wb') as current_file, # Write in bytes to get rid of ^M (newline) characters
        open(sources_file, 'r', encoding='utf-8') as in_file,
        open(merged_file, 'w', encoding='utf-8') as aggregate_file
    ):
        for line in lines: current_file.write(line.encode('utf-8')) # Iterate since lists don't support encode

        accumulator = ''
        for key in citation_verses:
            accumulator += f'@article{{{key}, journal = {{{citation_verses[key]}}}}}\n' 
        aggregate_file.writelines(in_file.readlines())
        aggregate_file.writelines(accumulator)

if __name__ == '__main__':
    main()
