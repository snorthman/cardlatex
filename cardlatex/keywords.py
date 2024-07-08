import re


class Keywords:
    def __init__(self, **kwargs):
        self._m: bool = kwargs['@multiline']
        self._keywords = {kw['@key']: kw['@value'] for kw in kwargs['keyword']}

    def __str__(self):
        m = ' (multiline)' if self._m else ''
        return f'Keywords {m}: [' + ', '.join(self._keywords.keys()) + ']'

    def _apply(self, string: str):
        replace: dict[tuple[int, int], str] = {}
        reserved: set[int] = set()
        for key, word in self._keywords.items():
            try:
                for m in re.finditer(key, string):
                    if string == '':
                        return word

                    w = word
                    while mm := re.search(r'#(\d)', w):
                        l, r = mm.span()
                        w = w[:l] + m.group(int(mm.group(1))) + w[r:]

                    reservation = set(range(*m.span()))
                    if not reserved.intersection(reservation):
                        replace[(min(reservation), max(reservation))] = w
                        reserved.update(reservation)
            except re.error as e:
                raise ValueError(f'Regex error:     "{e.msg}"\nInvalid keyword: "{key}"')
        # guaranteed no overlap in replace keys now
        c, result = 0, ''
        for l, r in sorted(replace, key=lambda a: a[0]):
            result += string[c:l] + replace[(l, r)]
            c = r + 1

        return result + string[c:]

    def apply(self, string: str):
        string_list = [string] if self._m else string.split('\n')
        for s in range(len(string_list)):
            string_list[s] = self._apply(string_list[s])
        return '\n'.join(string_list)
