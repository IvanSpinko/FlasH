"""The core: FlasH's logic with no UI and no storage.

- model: Question and Deck
- extract: PDF/TXT/MD files to lines of text
- parser: lines to questions, for ready-made test banks
- generator: questions from plain notes, offline
- ai: questions from plain notes with Claude (optional, needs internet)
- importer: file to questions, using the modules above
- quiz: choosing questions and running a test
"""
