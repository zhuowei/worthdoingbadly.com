import sys
# generates a table of contents from a markdown post.
# python3 _gentoc.py input.md
def slugify(a):
	b = ""
	for c in a.lower():
		if c.isalnum():
			b += c
		else:
			if b[-1] != "-":
				b += "-"
	if b[-1] == "-":
		b = b[:-1]
	return b
count = 1
print('<div style="font-size: 14px; background-color: #e8f5e9; display: inline-block" markdown="block">\nTable of Contents\n')
with open(sys.argv[1], "r") as infile:
	for l in infile:
		if l[0] != "#":
			continue
		l = l[1:].strip()
		slug = slugify(l)
		print("{}. [{}](#{})".format(count, l, slug))
		count += 1
print('</div>')
