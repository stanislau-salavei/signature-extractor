# Original prompt v2 (specification)

A copy of `/workspace/prompt/v2` as of 2026-11-19 (remark 91): stages 0–6, `final_prompt_ru.md`, `CHANGES.md` and the strings
table `i18n/strings_ru_en.csv` / `.xlsx`. These are **not** the app sources. Tests compare the app table
`i18n/strings_ru_en.csv` with this copy; the approved differences are listed in `tests/i18n_prompt_diff.py` and in
`NOTES.md`. Paths like `/workspace/...` in the text refer to the author's work machine; the mockups (PNG/HTML) are not
in the repository. The copy's files are not edited; the exception is remark 110 (version 1.0.1): three unused sample
rows from the mockups (`export.path_example`, `color.example_purple`, `color.example_burgundy`) were removed from
`i18n/strings_ru_en.csv` and the note of `color.name_placeholder` was fixed. On 2026-11-20 the user name in the sample
path of `export.path_example` in `i18n/strings_ru_en.xlsx` was replaced with a neutral «User» (in the source copy too).
The specification files themselves stay in Russian: they are the original source the tests compare against.
