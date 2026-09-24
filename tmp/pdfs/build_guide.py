from pathlib import Path
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

OUT = Path('output/pdf')
OUT.mkdir(parents=True, exist_ok=True)
FONT = Path('C:/Windows/Fonts')
pdfmetrics.registerFont(TTFont('Guide', str(FONT/'segoeui.ttf')))
pdfmetrics.registerFont(TTFont('GuideBold', str(FONT/'segoeuib.ttf')))
pdfmetrics.registerFontFamily('Guide', normal='Guide', bold='GuideBold')
NAVY = colors.HexColor('#142331'); RED = colors.HexColor('#D94B44')
INK = colors.HexColor('#263847'); MUTED = colors.HexColor('#526575'); LIGHT = colors.HexColor('#EDF5F7')
W,H = 612,792
c = canvas.Canvas(str(OUT/'Pokemon-Collection-Getting-Started.pdf'), pagesize=(W,H))
c.setTitle('Pokémon Collection | Getting Started')
c.setAuthor('Altylab')
styles = {
 'body': ParagraphStyle('body', fontName='Guide', fontSize=10.5, leading=14.8, textColor=INK),
 'small': ParagraphStyle('small', fontName='Guide', fontSize=9.3, leading=13, textColor=MUTED),
 'head': ParagraphStyle('head', fontName='GuideBold', fontSize=14, leading=18, textColor=NAVY),
}
y=0

def para(text, style='body', gap=7, x=42, width=528):
 global y
 p=Paragraph(text, styles[style]); _,height=p.wrap(width,700)
 if y-height < 48: raise RuntimeError(f'Page overflow: {text[:60]} at {y-height}')
 p.drawOn(c,x,y-height); y-=height+gap

def heading(text):
 global y
 y-=5; para(text,'head',7)

def step(n,text):
 para(f'<font color="#087F9A"><b>{n}.</b></font>  '+text, gap=7)

def note(title,text):
 global y
 p=Paragraph(f'<b>{title}</b><br/>'+text, styles['body']); _,height=p.wrap(500,700)
 c.setFillColor(LIGHT); c.roundRect(42,y-height-21,528,height+21,7,fill=1,stroke=0)
 p.drawOn(c,56,y-height-10); y-=height+32

def start(number,title,subtitle):
 global y
 c.setFillColor(NAVY); c.rect(0,H-120,W,120,fill=1,stroke=0)
 c.setFillColor(RED); c.rect(0,H-124,W,4,fill=1,stroke=0)
 c.setFillColor(colors.HexColor('#8BD9E7')); c.setFont('GuideBold',10)
 c.drawString(42,H-28,'ALTYLAB  /  POKÉMON COLLECTION')
 c.setFillColor(colors.white); c.setFont('GuideBold',25); c.drawString(42,H-67,title)
 c.setFont('Guide',10.5); c.drawString(42,H-93,subtitle)
 c.setStrokeColor(colors.HexColor('#D8E2E7')); c.line(42,39,570,39)
 c.setFont('Guide',8.3); c.setFillColor(MUTED)
 c.drawString(42,25,'Getting started  |  September 18, 2026')
 c.drawRightString(570,25,f'{number} / 3')
 y=H-146

start(1,'Your collection starts here','Track your cards, organize storage, and see what your decks still need.')
para('<link href="https://cards.altylab.com" color="#087F9A"><b>OPEN THE APP: cards.altylab.com</b></link>',gap=12)
note('Your own save','Your account starts empty. Your cards, quantities, locations, and saved decks are separate from everyone else’s. Use the same approved email on your phone and computer to access the same save.')
heading('1 / Sign in')
step(1,'Open the link above in your browser.')
step(2,'Choose <b>Sign in with Google</b> and select the Gmail account that was invited. Or enter that email and choose <b>Send login code</b>, then enter the code from your inbox.')
step(3,'Keep using that exact email address. A different email or alias is a different account. An internet connection is required.')
heading('2 / Find your way around')
for title, text in [
 ('Search','Find cards in the English catalog and record how many you own.'),
 ('Collection','Browse your owned cards, edit quantities, and organize locations.'),
 ('Decks','Paste a deck list, compare it with your cards, and save it.'),
 ('Need Cards','See the combined missing-card list for your saved decks.')]:
 para(f'<b>{title}</b> - {text}',gap=6)
heading('3 / Add your first cards')
step(1,'Open <b>Search</b>. Enter a card name, set code, set name, or collector number. Use <b>Set</b> and <b>Card type</b> to narrow the results.')
step(2,'If a card is missing, change <b>Format</b> to <b>Any format</b> or reset filters. The default Standard filter can hide older cards.')
step(3,'Check the artwork, set, and card number against your physical card. Under <b>CURRENT OWNED</b>, use + / - or enter your total quantity and tap outside the box. Wait for <b>Saved</b>.')
para('<b>Example:</b> If you own 3 copies and get 2 more, set the quantity to <b>5</b>. This number is your total, not the number you are adding.','small')
c.showPage()

start(2,'Organize cards & check decks','Keep a useful digital binder and compare deck lists with your real cards.')
heading('Browse and correct your collection')
para('Open <b>Collection</b> to see your owned cards. Search by name, set, or number; organize by <b>Typing</b>, <b>A-Z</b>, or <b>Set</b>; and filter or sort the view. <b>Recently added</b> helps you find new entries.')
para('Tap anywhere on a card tile, including its artwork, to open its details. Set <b>Quantity owned</b>, then tap <b>Save quantity</b>. Setting it to zero removes it from your owned-card view; review the confirmation when shown.')
heading('Use locations for boxes and binders')
step(1,'Open <b>Manage</b> beside Locations, or <b>Manage locations</b> in a card’s details. Name a location, such as “Main Box” or “Trade Binder,” and choose <b>Add location</b>.')
step(2,'In a card’s details, choose a location, enter <b>Copies in this location</b>, and tap <b>Save location quantity</b>. You can split owned copies across locations.')
step(3,'For a batch, choose <b>Select cards to change location</b>, select cards, then <b>Change location</b>. Pick the source, destination, and whether to move one or every available copy, then confirm.')
para('With one active location, new cards default there. With zero or multiple locations, they start <b>Unassigned</b>. Moving cards changes where they are stored, not how many you own.','small')
heading('Check and save a deck')
step(1,'Copy a text deck list from Pokémon TCG Live or Limitless. Open <b>Decks</b> and choose <b>+ Check a new deck</b>.')
step(2,'Paste the list and select <b>Check my inventory</b>. Review owned and missing quantities and any lines that need correction. Checking does not add cards to your collection.')
step(3,'Give it a <b>Deck name</b> and select <b>Save to deck library</b>. You can save a deck even when you do not own every card, once any list-format errors are fixed.')
heading('Reopen, edit, or share a saved deck')
para('Tap a saved deck to recheck it against your current collection. Use <b>Show decks</b> if Saved Decks is collapsed. The <b>three-dot menu</b> contains <b>Edit deck list</b>, <b>Rename</b>, and <b>Remove deck</b>. After editing, check again and select <b>Update saved deck</b>. Use <b>Copy deck list</b> to share the text.')
para('<b>Matching rules:</b> Pokémon use the requested printing or a gameplay-identical alternate artwork. Trainers and Special Energy match by name. Basic Energy is ignored by the inventory check, so check that supply yourself.','small')
c.showPage()

start(3,'See what you need','Use your saved decks to plan purchases, then keep your quantities up to date.')
heading('Build a missing-card list')
step(1,'Add your owned cards and save the decks you want to build.')
step(2,'Open <b>Need Cards</b>. It combines shortages from your saved decks and shows copies needed, unique cards, and decks affected.')
step(3,'Use <b>Refresh list</b> after changes. When you acquire a card, update its owned quantity in <b>Search</b> or <b>Collection</b>, then refresh the list.')
note('One physical copy, one deck assignment','Saving a deck labels available owned copies for that deck. The same copy is not automatically allocated to two decks. For example, two saved decks needing 4 copies each require 8 copies to keep both built at once. These labels do not change your total quantity or storage location.')
para('Use <b>Allocate to Decks</b> in Collection to allocate available cards across saved decks. You can also select a deck under <b>Deck Lists</b> in Collection to view its cards and edit its list. A single-deck check and the combined Need Cards list can differ because the combined list accounts for copies already assigned elsewhere.')
heading('Export or import your collection')
para('<b>Export:</b> In Collection, choose <b>JSON</b> for a structured collection file or <b>CSV</b> for a spreadsheet-friendly copy. Keep one if you want your own record of the cards and quantities.')
para('<b>Import:</b> Choose <b>Import</b>, select a supported exported CSV or JSON file, choose a mode, and select <b>Preview changes</b>. Review the changes before <b>Apply import</b>.')
para('<b>Update listed cards</b> changes only cards in the file. <b>Restore / replace</b> makes your collection match the file, including removing cards not listed. Use it only when that is your intention.')
para('Collection exports are not a full account backup: they do not include saved deck lists or storage-location assignments. Use <b>Copy deck list</b> to keep a separate copy of a deck. Automatic server backups also protect account databases.','small')
heading('A few useful tips')
para('<b>On a phone:</b> Use the bottom navigation. Collection’s mobile filters include type, set, location, sorting, and compact or larger card sizes. You can bookmark the site or add a browser shortcut to your home screen.')
para('<b>Cannot sign in?</b> Check that you selected the invited email. Try the emailed login code if Google sign-in fails, and check spam or junk folders for the code.')
para('<b>Current scope:</b> The app tracks English catalog printings and quantities. It does not separately track finish or condition, and a deck inventory check is not a complete tournament-legality check. If something looks wrong, send Eric the page name and what happened.','small')
c.save()
print(OUT/'Pokemon-Collection-Getting-Started.pdf')
