def readlines(filename):
    with open(filename, "r") as infile:
        alllines = [l.strip().split("!!!!") for l in infile]
    return alllines

alllines = readlines("appkitpkgs_output.txt") + readlines("foundationpkgs.txt") + readlines("cfpkgs.txt")

def pullbundleid(s):
    if "jumptable" in s and "ComTwitterTwit" in s:
        # ida is drunk
        return "com.twitter.twitter-mac"
    if s.endswith("ComAppleIstMer"):
        return "com.apple.ist.Merlin"
    if s.endswith("cfstr_JpCoPfuScansna"):
        return "jp.co.pfu.ScanSnap.ScantoEvernote1"
    if s.endswith("ComAppleLogicP"):
        return "com.apple.logic.pro"
    if s.endswith("cfstr_ComOmnigroupOm_0"):
        return "com.omnigroup.OmniOutlinerPro3"
    if s.endswith("cfstr_ComOmnigroupOm_2"):
        return "com.omnigroup.OmniFocus.MacAppStore"
    if s.endswith("cfstr_ComAppleIweb"):
        return "com.apple.iWeb"
    return s[s.find("; ") + 3:-1]

alllines2 = [(a[0], a[1], pullbundleid(a[2])) for a in alllines]
alllines2.sort(key=lambda a: a[2])

def outputHTML():

    HTMLHEAD = """
    <!DOCTYPE html>
    <html>
    <head>
    <script src="https://cdn.jsdelivr.net/npm/sorttable@1.0.2/sorttable.js"></script>
    <style>body {font-family: monospace;}</style>
    <script>
    if(!(window.doNotTrack === "1" || navigator.doNotTrack === "1" || navigator.doNotTrack === "yes" || navigator.msDoNotTrack === "1")) {
    (function(i,s,o,g,r,a,m){i['GoogleAnalyticsObject']=r;i[r]=i[r]||function(){
    (i[r].q=i[r].q||[]).push(arguments)},i[r].l=1*new Date();a=s.createElement(o),
    m=s.getElementsByTagName(o)[0];a.async=1;a.src=g;m.parentNode.insertBefore(a,m)
    })(window,document,'script','https://www.google-analytics.com/analytics.js','ga');

    ga('create', 'UA-7810231-7', 'auto');
    ga('send', 'pageview');
    }
    </script>
    </head>
    <body>
    <p>Calls to __CFAppVersionCheckLessThan in AppKit/Foundation/CoreFoundation on macOS 10.13.4. Tap on a column header to sort.</p>
    <table class="sortable">
    <thead>
    <tr><th>Bundle ID</th><th>Method name</th><th>Caller method name</th>
    </thead>
    """

    print(HTMLHEAD)
    print("<tbody>")
    for l in alllines2:
        print("<tr><td>"+l[2] + "</td><td>"+ l[0] + "</td><td>" + l[1] + "</td></tr>")
    print("</tbody></table>")

if __name__ == "__main__":
    outputHTML()