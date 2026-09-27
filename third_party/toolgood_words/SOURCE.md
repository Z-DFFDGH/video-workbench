# ToolGood.Words Sensitive Word Data

- Project: ToolGood.Words
- Project URL: https://github.com/toolgood/ToolGood.Words
- Source archive provided by the user: `ToolGood.Words-master.zip`
- Source archive SHA-256: `6769927F293326BB26200BDFF7C6CDE3DAB872E04A014623C1DEFBD556F134D7`
- Original data file: `csharp/ToolGood.Words.Test/_Illegal/IllegalKeywords.txt`
- Original file SHA-256: `1B69E2691AA81F2526C42D0436BAB55BB1B219596B128312FBEF2B47A12CD76D`
- License: Apache License 2.0, see `LICENSE` in this directory

## Usage

The application uses this data as its editable local sensitive word list. It does
not include the ToolGood.Words matching library, pinyin logic, variant handling,
or any other source code from the project.

## Modifications

For the application file `sensitive_words.txt`, blank lines were removed and
case-insensitive duplicate entries were collapsed while preserving the first
occurrence. The normalized file contains 10,220 UTF-8 entries without a BOM.
