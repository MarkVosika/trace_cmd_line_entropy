# import the basic python packages we need
import os
import sys
import json
import math
import time
import binascii
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from cryptography.fernet import Fernet
import requests 
from openpyxl import Workbook
from openpyxl.styles import Font
import urllib
import urllib3
from requests.auth import HTTPBasicAuth
requests.packages.urllib3.disable_warnings()

#___________________________________________________________________________________________________________________________________

#empty variables for handling encryption
key = ""
uncipher_text = ""
cipher_suite = ""
encryptedpwd = ""

base_url = 'https://<server>.com'	
username = '<base64_username>'
key = '<base64_fernet_key>'
cipher_suite = Fernet(key)
with open('<path to cipher text file>', 'rb') as file_object2:
	for line in file_object2:
		encryptedpwd = line

#___________________________________________________________________________________________________________________________________

#authenticate to host
http = urllib3.PoolManager()
handshake = HTTPBasicAuth(binascii.a2b_base64(username).strip(), binascii.a2b_base64((cipher_suite.decrypt(encryptedpwd))).strip())
r = requests.post(base_url + '/auth',verify=False,auth=handshake)
sessionid = r.content
print (sessionid)
file_object2.close()

#___________________________________________________________________________________________________________________________________

#get details about a saved question by name and load the JSON results into python
saved_question = requests.get(base_url + '/api/v2/saved_questions/by-name/Trace_Executed_Processes_1hour',verify=False, headers={'session': sessionid})
json_input = (json.dumps(saved_question.json(), indent=4, sort_keys=True, ensure_ascii=False))
json_load = json.loads(json_input)

#___________________________________________________________________________________________________________________________________

#extract out the id number for the saved question
id_num =''

for k,v in json_load["data"].items():
	if k == 'id':
		id_num = str(v)

#___________________________________________________________________________________________________________________________________

#sleep to allow the results to come back
print ("\nwaiting 60 seconds before getting the results....") 
time.sleep(60)

#___________________________________________________________________________________________________________________________________

#ask the question reference the id number and load the JSON results into python
saved_question = requests.get(base_url + '/api/v2/result_data/saved_question/' + id_num ,verify=False, headers={'session': sessionid})
json_input = (json.dumps(saved_question.json(), indent=4, sort_keys=True, ensure_ascii=False))
json_load = json.loads(json_input)

#___________________________________________________________________________________________________________________________________

#parse through the results getting pulling back a list of column headers

column_header = []
cmd_line_list = []
threshold_match = []

for lst in json_load["data"]["result_sets"][0]["columns"]:
	column_header.append(lst["name"].encode("utf-8"))

#___________________________________________________________________________________________________________________________________

# function calculates shannon entropy for a list of strings			
def shannon(word):
	entropy = 0.0
	length = len(word)

	occ = {}
	for c in word :
		if not c in occ:
			occ[ c ] = 0
		occ[c] += 1

	for (k,v) in occ.items():
		p = float( v ) / float(length)
		entropy -= p * math.log(p, 2) # Log base 2
	return entropy

#___________________________________________________________________________________________________________________________________

# from the results extracts out the Command Line parameter out and calculates entropy for it, then if the value over the threshold, writes the entire row of info to a new list. 
for cmd in json_load["data"]["result_sets"][0]["rows"]:
	cmd_line = cmd['data'][6][0]['text']
	entropy = shannon(cmd_line)
	print (entropy)
	value = 5.75
	if entropy > value:
		threshold_match.append(cmd_line)

#_____________________________________________________________________________________________________________________________________________

# for absolute time range 

time_now = int(round(time.time() * 1000))
time_2h_ago = int(round((time.time() - 2 * 60 * 60)* 1000))
time_range = str(time_2h_ago)+'|'+str(time_now)

#_____________________________________________________________________________________________________________________________________________

# get source hash
r = requests.get(base_url + "/api/v2/sensors/by-name/" + urllib.parse.quote("Trace Executed Processes"), headers={'session':sessionid}, verify=False)
sensor_object = json.dumps(r.json(), indent=4, sort_keys=True, ensure_ascii=False)
json_load = json.loads(sensor_object)

source_hash = json_load['data']['hash']

#_____________________________________________________________________________________________________________________________________________

full_trace_return= []
data = []
print (len(threshold_match))
if len(threshold_match) > 15:
	sys.exit()
elif len(threshold_match) > 0:
	for match in threshold_match:
		print ("\n\nAsking Question for Entropy Threshold Match... \n\n")
		print (match)

		#Create JSON body with hardcoded Trace parameters
		sensor_obj = {}
		sensor_obj["source_hash"] = source_hash
		sensor_obj["name"] = "Trace Executed Processes"
		sensor_obj["parameters"] = [{"key":"||TimeRange||","value":"absolute time range"},{"key":"||AbsoluteTimeRange||","value":time_range},{"key":"||TreatInputAsRegEx||","value":"0"},{"key":"||OutputYesOrNoFlag||","value":"0"},{"key":"||MaxResultsPerHost||","value":"10"},{"key":"||MakeStackable||","value":"0"},{"key":"||ProcessPath||","value":""},{"key":"||ParentProcessPath||","value":""},{"key":"||CommandLine||","value":match},{"key":"||MD5||","value":""},{"key":"||Domain||","value":""},{"key":"||Username||","value":""}]
		body = {}
		body["selects"] = [{"sensor":sensor_obj}]
	
#_____________________________________________________________________________________________________________________________________________

		#ask the question using the returned parsed json
		api_path = '%s/api/v2/questions' % base_url
		connectionsReq = requests.post(api_path, verify=False, headers={'session': sessionid}, json=body)
		json_data = (json.dumps(connectionsReq.json()))

#_____________________________________________________________________________________________________________________________________________

		#get the question id from the asked question
		json_raw = json.loads(json_data)
		question_id = json_raw["data"]["id"]

#_____________________________________________________________________________________________________________________________________________

		#sleep to allow the results to come back
		print ("\nwaiting 60 seconds before getting the results....") 
		time.sleep(60)

#_____________________________________________________________________________________________________________________________________________

		#query the resultxml
		api_path = '%s/api/v2/result_data/question/%d?json_pretty_print=1' % (base_url, question_id)
		connectionsReq = requests.get(api_path, verify=False, headers={'session': sessionid})
		json_data = (json.dumps(connectionsReq.json(), indent=4, sort_keys=True))
		full_trace_return.append(json_data)

#_____________________________________________________________________________________________________________________________________________
		
		#parse out question result data and append to lists
		temp = []
		header = []

		if len(threshold_match) > 0:
			for json_item in full_trace_return:
				json_load = json.loads(json_item)
			for i in json_load["data"]["result_sets"][0]["columns"]:
				for k,v in i.items():
					if k == "name":
						header.append(v)
			for i in json_load["data"]["result_sets"][0]["rows"]:
				for k,v in i.items():
					if k == "data" and v[0][0]['text'] != "[no results]" and v[0][0]['text'] != "Sensor requires Trace schema version 14 or higher. Update Trace Tools on endpoint" :
						for lst in v:
							temp.append(lst[0]['text'])
			data.append(temp)

#_____________________________________________________________________________________________________________________________________________

#writer header and data to excel file

if len(data) > 0:

	excel_file = 'Entropy_match.xlsx'  # setup path for excel file
	bold_font = Font(bold = True)		#set bold font variable

	wb = Workbook()		#open workbook
	sheet1 = wb['Sheet']
	sheet1.append(header)
	for cell in sheet1["1:1"]:
		cell.font = bold_font
	for lst in data:
		sheet1.append(lst)
	wb.save(excel_file) 	#save workbook

#_____________________________________________________________________________________________________________________________________________

#email the spreadsheet off

	recipient_list = ['user@domain.com']

	for recipient in recipient_list:

		email_sender = 'tanium@domain.com'
		email_recipient = recipient

		subject = 'High Entropy | CMD Line'

		msg = MIMEMultipart()
		msg['From'] = email_sender
		msg['To'] = email_recipient
		msg['Subject'] = subject

		body = 'See attached cmd lines with high entropy...'
		msg.attach(MIMEText(body,'plain'))

		filename = 'Entropy_match.xlsx'
		attachment  =open(excel_file,'rb')

		part = MIMEBase('application','octet-stream')
		part.set_payload((attachment).read())
		encoders.encode_base64(part)
		part.add_header('Content-Disposition',"attachment; filename= "+filename)

		msg.attach(part)
		text = msg.as_string()
		server = smtplib.SMTP('<mail_server>',25)
		server.starttls()
		#server.login(email_user,email_password)


		server.sendmail(email_sender,email_recipient,text)
		server.quit()
		
#___________________________________________________________________________________________________________________________________

#close file handles and remove files
	attachment.close()
	os.remove(excel_file)
