import sublime, sublime_plugin, re
import time
import threading
from math import ceil as ceil
from os.path import basename

Pref = {}
s = {}
wsd = {'modified':True, 'selection':True, 'syntax':'plain text','changes':-1,'status':-1}

def plugin_loaded():
	global s, Pref
	s = sublime.load_settings('DailyJournalTimesheet.sublime-settings')
	Pref = Pref()
	Pref.load();
	s.clear_on_change('reload')
	s.add_on_change('reload', lambda:Pref.load())

	if not 'running_tstotaltime_loop' in globals():
		global running_tstotaltime_loop
		running_tstotaltime_loop = True
		t = threading.Thread(target=tstotaltime_loop)
		t.start()

class Pref:
	def load(self):
		Pref.view                   = False
		Pref.elapsed_time           = 0.4
		Pref.running                = False

		Pref.enable_live_count      = s.get('enable_live_count', True)
		Pref.enable_readtime        = s.get('enable_readtime', False)

		for window in sublime.windows():
			for view in window.views():
				view.erase_status('DailyJournalTimesheet');
				view.settings().erase('DailyJournalTimesheet')

class DailyJournalTimesheet(sublime_plugin.EventListener):

	def should_run_with_syntax(self, view):
		vs =  view.settings()

		syntax = vs.get('syntax')
		syntax = basename(syntax).split('.')[0].lower() if syntax != None else "plain text"

		ws = vs.get('DailyJournalTimesheet', wsd)
		ws['syntax'] = syntax
		vs.set('DailyJournalTimesheet', ws)

		return True

	def on_activated_async(self, view):
		self.asap(view)

	def on_post_save_async(self, view):
		self.asap(view)

	def on_modified_async(self, view):
		vs = view.settings()
		ws = vs.get('DailyJournalTimesheet', wsd)
		ws['modified'] = True
		vs.set('DailyJournalTimesheet', ws)

	def on_selection_modified_async(self, view):
		vs = view.settings()
		ws = vs.get('DailyJournalTimesheet', wsd)
		ws['selection'] =  True
		vs.set('DailyJournalTimesheet', ws)

	def on_close(self, view):
		Pref.view = False

	def asap(self, view):
		Pref.view = view
		Pref.elapsed_time = 0.4
		sublime.set_timeout(lambda:DailyJournalTimesheet().run(True), 0)

	def run(self, asap = False):
		if not Pref.view:
			self.guess_view()
		else:
			view = Pref.view
			vs = view.settings()
			ws = vs.get('DailyJournalTimesheet', wsd)
			if vs.get('is_widget') or not ws: # (if not ws)WTF, happens when closing a view
				self.guess_view()
			else:
				if (ws['modified'] or ws['selection']) and (Pref.running == False or asap) and self.should_run_with_syntax(view):
					sel = view.sel()
					if sel:
						if len(sel) == 1 and sel[0].empty():
							if not Pref.enable_live_count or view.size() > 10485760:
								view.erase_status('DailyJournalTimesheet')
							elif view.change_count() != ws['changes']:
								ws['changes'] = view.change_count()
								#  print('running:'+str(view.change_count()))
								DailyJournalTimesheetThread(view, [view.substr(sublime.Region(0, view.size()))], view.substr(view.line(view.sel()[0].end())), False).start()
							else:
								# print('running from cache:'+str(view.change_count()))
								view.set_status('DailyJournalTimesheet', 'TSTotalTime: ' + str(ws['TSTotalTime']))
						else:
							try:
								DailyJournalTimesheetThread(view, [view.substr(sublime.Region(s.begin(), s.end())) for s in sel], view.substr(view.line(view.sel()[0].end())), True).start()
							except:
								pass
						ws['modified'] = False
						ws['selection'] = False
						vs.set('DailyJournalTimesheet', ws)


	def guess_view(self):
		if sublime.active_window() and sublime.active_window().active_view():
			Pref.view = sublime.active_window().active_view()

	def display(self, view, on_selection, tstotaltime):
		view.set_status('DailyJournalTimesheet', 'TSTotalTime: ' + str(tstotaltime))

	def makePlural(self, word, count):
		return "%s %s%s" % (count, word, ("s" if count != 1 else ""))

class DailyJournalTimesheetThread(threading.Thread):

	def __init__(self, view, content, content_line, on_selection):
		threading.Thread.__init__(self)
		self.view = view
		self.content = content
		self.content_line = content_line
		self.on_selection = on_selection

		self.char_count = 0
		self.tstotaltime_line = 0
		self.chars_in_line = 0

		ws = view.settings().get('DailyJournalTimesheet', wsd)
		self.syntax = ws['syntax']

	def run(self):
		# print ('running:'+str(time.time()))
		Pref.running         = True

		self.tstotaltime = sum([float(x) for x in re.findall("TSTime: ([0-9.]+)", ''.join(self.content))])

		if not self.on_selection:
			vs = self.view.settings()
			ws = vs.get('DailyJournalTimesheet', wsd)
			ws['TSTotalTime'] = self.tstotaltime
			vs.set('DailyJournalTimesheet', ws)

		sublime.set_timeout(lambda:self.on_done(), 0)

	def on_done(self):
		try:
			DailyJournalTimesheet().display(self.view, self.on_selection, self.tstotaltime)
		except:
			pass
		Pref.running = False

	def count(self, content):

		# begin = time.time()

		#=====1
		# wrdRx = Pref.wrdRx
		# """counts by counting all the start-of-word characters"""
		# # regex to find word characters
		# matchingWrd = False
		# words = 0
		# space_symbols = [' ', '\r', '\n']
		# for ch in content:
		# # 	# test if this char is a word char
		# 	isWrd = ch not in space_symbols
		# 	if isWrd and not matchingWrd:
		# 		words = words + 1
		# 		matchingWrd = True
		# 	if not isWrd:
		# 		matchingWrd = False

		#=====2
		wrdRx = Pref.wrdRx
		splitRx = Pref.splitRx
		if splitRx:
			words = len([1 for x in splitRx(content) if False == x.isdigit() and wrdRx(x)])
		else:
			words = len([1 for x in content.replace("'", '').replace('—', ' ').replace('–', ' ').replace('-', ' ').split() if False == x.isdigit() and wrdRx(x)])

		# Pref.elapsed_time = end = time.time() - begin;
		# print ('Benchmark: '+str(end))

		return words

def tstotaltime_loop():
	tstotaltime = DailyJournalTimesheet().run
	while True:
		# sleep time is adaptive, if takes more than 0.4 to calculate the word count
		# sleep_time becomes elapsed_time*3
		if Pref.running == False:
			sublime.set_timeout(lambda:tstotaltime(), 0)
		time.sleep((Pref.elapsed_time*3 if Pref.elapsed_time > 0.4 else 0.4))
