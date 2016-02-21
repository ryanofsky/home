// Scrape http://www.cliffsnotes.com/literature/b/the-brothers-karamazov/book-summary
function dump(data, filename) {
    if(!data) {
        console.error('Console.save: No data');
        return;
    }

    if(!filename) filename = 'console.json';

    if(typeof data === "object"){
        data = JSON.stringify(data, undefined, 4);
    }

    var blob = new Blob([data], {type: 'text/json'}),
        e    = document.createEvent('MouseEvents'),
        a    = document.createElement('a');

    a.download = filename;
    a.href = window.URL.createObjectURL(blob);
    a.dataset.downloadurl =  ['text/json', a.download, a.href].join(':');
    e.initMouseEvent('click', true, false, window, 0, 0, 0, 0, 0, false, false, false, false, 0, null);
    a.dispatchEvent(e);
}

$("div#abstractAd").remove();
var art = $("article.copy");
var sign = $("li.sign-post");
if (art.length == 1 && sign.length) {
  var title = $("a", sign).text();
  dump('<meta charset="utf-8" />\n\n' + $("<a>").attr("href", window.location).text(window.location).addClass("scrape-url")[0].outerHTML + "\n\n" + art[0].outerHTML, title + ".html");
  window.location = $($("i.icon-Arrow_next")[1]).parent()[0].href;
}

// Scrape http://www.sparknotes.com/lit/brothersk/
$("div.floatingad").remove();
var dtitle = $("div.next-title");
var dtext = $("div.studyGuideText");
if (dtitle.length == 1 && dtext.length == 1) {
  dump('<meta charset="utf-8" />\n\n' + $("<h3>").text(dtitle.text()).addClass("scrape-title")[0].outerHTML + "\n\n" + dtext[0].outerHTML, dtitle.text() + ".html");
  window.location = $("a.right.arrow-nav.next").attr("href");
}

// number sections
/*
i=1
while read F; do
  mv -iv "$F" "$(printf "%02i" $i)-$F"
  i=$((i+1))
done < <(ls -1tr *.html)
*/

// Consolidate saved html
/*
rm -v 00-toc.html _index
for F in *.html; do
  echo "<a href=\"$F\">${F%.html}</a><br/>" >> _index
done
cat > 00-toc.html <<< "<meta charset="utf-8" />
<h1>Table of Contents</h1>"
cat _index >> 00-toc.html
rm -v _index
*/
