from tkinter import *
from PIL import Image, ImageTk
from tkinter import messagebox
from tkinter import filedialog
from tkinter.scrolledtext import ScrolledText
import xml.etree.ElementTree as et
import xmltodict
import uuid
import os
import seaborn as sns
import shutil
import json
import copy
# import analysis as an
import sqlite3 as lite
import numpy as np
import matplotlib.pyplot as plt

class BackendWindow(Frame):
    def __init__(self, master, output_path):
        """
        does backend analysis
        """

        self.master = Toplevel(master)
        self.master.title('Backend Analysis')
        self.output_path = output_path
        self.master.geometry('+0+700')
        self.get_cursor()
        self.get_id_proto_dict()
        self.get_start_times()

        self.guide()
        self.view_hard_limit = 100
        self.scroll_limit = 30
        Label(self.master, text='Choose backend analysis type:').pack()

        raw_table_button = Button(self.master, text='Navigate Raw Tables', command=lambda : self.view_raw_tables())
        raw_table_button.pack()

        material_flow_button = Button(self.master, text='Get Material Flow', command=lambda : self.view_material_flow())
        material_flow_button.pack()

        commodity_transfer_button = Button(self.master, text='Get Commodity Flow', command=lambda : self.commodity_transfer_window())
        commodity_transfer_button.pack()

        deployment_of_agents_button = Button(self.master, text='Get Prototype Deployment', command=lambda : self.agent_deployment_window())
        deployment_of_agents_button.pack()

        facility_inventory_button = Button(self.master, text='Get Facility Inventory', command=lambda : self.facility_inventory_window())
        facility_inventory_button.pack()

        timeseries_button = Button(self.master, text='Get Timeseries', command=lambda : self.timeseries_window())
        timeseries_button.pack()


    def get_start_times(self):
        i = self.cur.execute('SELECT * FROM info').fetchone()
        self.init_year = i['InitialYear']
        self.init_month = i['InitialMonth']
        self.duration = i['Duration']
        i = self.cur.execute('SELECT * FROM TimeStepDur').fetchone()
        self.dt = i['DurationSecs']


    def get_id_proto_dict(self):
        agentids = self.cur.execute('SELECT agentid, prototype, kind FROM agententry').fetchall()
        self.id_proto_dict = {}
        for agent in agentids:
            if agent['kind'] == 'Facility':
                self.id_proto_dict[agent['agentid']] = agent['prototype']


    def get_cursor(self):
        con = lite.connect(os.path.join(self.output_path, 'cyclus.sqlite'))
        con.row_factory = lite.Row
        self.cur = con.cursor()


    def view_raw_tables(self):
        self.raw_table_window = Toplevel(self.master)
        self.raw_table_window.title('Navigate Raw Tables')
        self.raw_table_window.geometry('+0+3500')
        # just like a sql query with ability to export and stuff
        self.guide_text = ''


    def view_material_flow(self):
        self.guide_text = ''
        # show material trade between prototypes
        self.material_flow_window = Toplevel(self.master)
        self.material_flow_window.title('List of transactions to view')
        self.material_flow_window.geometry('+700+1000')
        parent = self.material_flow_window

        traders = self.cur.execute('SELECT DISTINCT senderid, receiverid, commodity FROM transactions').fetchall()
        table_dict = {'sender': [],
                      'receiver': [],
                      'commodity': []}
        parent = self.assess_scroll_deny(self, len(traders), self.material_flow_window)
        if parent == -1:
            return
        if len(traders) > self.view_hard_limit:
            messagebox.showinfo('Too much', 'You have %s distinct transaction sets.. Too much for me to show here' %str(len(traders)))
            self.material_flow_window.destroy()
            return
        if len(traders) > self.scroll_limit:
            parent = self.add_scrollbar(self.material_flow_window)

        # create table of sender - receiverid - commodity set like:
        for i in traders:
            table_dict['sender'].append(self.id_proto_dict[i['senderid']] + '(%s)' %str(i['senderid']))
            table_dict['receiver'].append(self.id_proto_dict[i['receiverid']] + '(%s)' %str(i['receiverid']))
            table_dict['commodity'].append(i['commodity'])

        columnspan = 7
        Label(parent, text='List of transactions:').grid(row=0, columnspan=columnspan)
        Label(parent, text='Sender (id)').grid(row=1, column=0)
        Label(parent, text='').grid(row=1, column=1)
        Label(parent, text='Commodity').grid(row=1, column=2)
        Label(parent, text='').grid(row=1, column=3)
        Label(parent, text='Receiver (id)').grid(row=1, column=4)
        Label(parent, text=' ').grid(row=1, column=5)
        Label(parent, text='======================').grid(row=2, columnspan=columnspan)
             
        row = 3
        for indx, val in enumerate(table_dict['sender']):
            Label(parent, text=val).grid(row=row, column=0)
            Label(parent, text='->').grid(row=row, column=1)
            Label(parent, text=table_dict['commodity'][indx]).grid(row=row, column=2)
            Label(parent, text='->').grid(row=row, column=3)            
            Label(parent, text=table_dict['receiver'][indx]).grid(row=row, column=4)
            Button(parent, text='plot', command=lambda sender=val, receiver=table_dict['receiver'][indx], commodity=table_dict['commodity'][indx]: self.sender_receiver_action(sender, receiver, commodity, 'plot')).grid(row=row, column=5)
            Button(parent, text='export', command=lambda sender=val, receiver=table_dict['receiver'][indx], commodity=table_dict['commodity'][indx]: self.sender_receiver_action(sender, receiver, commodity, 'export')).grid(row=row, column=6)
            row += 1



    def sender_receiver_action(self, sender, receiver, commodity, action):
        sender_name = sender[:sender.index('(')]
        receiver_name = receiver[:receiver.index('(')]
        sender_id = sender[sender.index('(')+1:sender.index(')')]
        receiver_id = receiver[receiver.index('(')+1:receiver.index(')')]
        t = self.cur.execute('SELECT sum(quantity), time FROM transactions INNER JOIN resources ON transactions.resourceid == resources.resourceid where senderid=%s and receiverid=%s and commodity="%s" GROUP BY transactions.time' %(sender_id, receiver_id, commodity)).fetchall()
        x, y = self.query_result_to_timeseries(t, 'sum(quantity)')

        if action == 'plot':
            self.plot(x, y, '%s Sent' %commodity)
        elif action == 'export':
            self.export(x, y, '%s_%s_%s.csv' %(sender_name, receiver_name, commodity))
            

    def commodity_transfer_window(self):
        self.guide_text = ''
        self.commodity_tr_window = Toplevel(self.master)
        self.commodity_tr_window.title('Commodity Movement Window')
        self.commodity_tr_window.geometry('+700+1000')
        parent = self.commodity_tr_window
        
        commods = self.cur.execute('SELECT DISTINCT commodity FROM transactions').fetchall()
        names = []
        for i in commods:
            names.append(i['commodity'])
        names.sort(key=str.lower)
        if len(commods) > self.scroll_limit:
            parent = self.add_scrollbar(self.commodity_tr_window)

        columnspan = 3
        
        Label(parent, text='List of Commodities').grid(row=0, columnspan=columnspan)
        Label(parent, text='======================').grid(row=1, columns=columnspan)
        row = 2
        for i in names:
            Label(parent, text=i).grid(row=row, column=0)
            Button(parent, text='plot', command=lambda commod=i: self.commodity_transfer_action(commod, 'plot')).grid(row=row, column=1)
            Button(parent, text='export', command=lambda commod=i: self.commodity_transfer_action(commod, 'export')).grid(row=row, column=2)
            row += 1

    def commodity_transfer_action(self, commod, action):
        movement = self.cur.execute('SELECT time, sum(quantity) FROM transactions INNER JOIN resources on transactions.resourceid==resources.resourceid WHERE commodity="%s" GROUP BY time' %commod).fetchall()
        x, y = self.query_result_to_timeseries(movement, 'sum(quantity)')

        if action == 'plot':
            self.plot(x, y, '%s Sent' %commod)
        elif action == 'export':
            self.export(x, y, '%s.csv' %commod)


    def agent_deployment_window(self):
        """
        plots / exports prototype entry and exit
        """
        self.guide_text = ''

        self.agent_dep_window = Toplevel(self.master)
        self.agent_dep_window.title('Prototype Deployment / Exit Window')
        self.agent_dep_window.geometry('+700+1000')
        parent = self.agent_dep_window
        # s = bwidget.ScrolledWindow(self.agent_dep_window, auto='vertical', scrollbar='vertical')
        # f = bwidget.ScrollableFrame(s, constrainedwidth=True)
        # g = f.getframe()

        entry = self.cur.execute('SELECT DISTINCT prototype FROM agententry WHERE kind="Facility"').fetchall()
        proto_list = [i['prototype'] for i in entry]
        proto_list.sort(key=str.lower)
        if len(entry) > self.scroll_limit:
            parent = self.add_scrollbar(self.agent_dep_window)

        columnspan = 7
        

        Label(parent, text='List of Agents').grid(row=0, columnspan=columnspan)
        Label(parent, text='======================').grid(row=1, columnspan=columnspan)
        Label(parent, text='=====Plot=====').grid(row=2, columnspan=3)
        Label(parent, text='=====Export=====').grid(row=2, column=4, columnspan=3)
        row = 3
        for i in proto_list:
            Label(parent, text=i).grid(row=row, column=3)
            Button(parent, text='enter', command=lambda prototype=i : self.agent_deployment_action(prototype, 'plot', 'enter')).grid(row=row, column=0)
            Button(parent, text='exit', command=lambda prototype=i : self.agent_deployment_action(prototype, 'plot', 'exit')).grid(row=row, column=1)
            Button(parent, text='deployed', command=lambda prototype=i : self.agent_deployment_action(prototype, 'plot', 'deployed')).grid(row=row, column=2)
            Button(parent, text='enter', command=lambda prototype=i: self.agent_deployment_action(prototype, 'export', 'enter')).grid(row=row, column=4)
            Button(parent, text='exit', command=lambda prototype=i: self.agent_deployment_action(prototype, 'export', 'exit')).grid(row=row, column=5)
            Button(parent, text='deployed', command=lambda prototype=i: self.agent_deployment_action(prototype, 'export', 'deployed')).grid(row=row, column=6)
            row += 1


    def agent_deployment_action(self, prototype, action, which):
        entry = self.cur.execute('SELECT agentid, entertime FROM agententry WHERE prototype="%s"' %prototype).fetchall()
        agent_id_list = []
        entertime = []
        for i in entry:
            entertime.append(i['entertime'])
            agent_id_list.append(i['agentid'])
        exittime = []
        for i in agent_id_list:
            try:
                exit = self.cur.execute('SELECT agentid, exittime FROM agentexit WHERE agentid=%s' %str(i)).fetchone()
            except:
                # agentexit table doesn't exist
                continue
            if exit == None:
                exittime.append(-1)
            else:
                exittime.append(exit['exittime'])
        x = np.array(list(range(self.duration)))
        y = []
        if which == 'enter':
            for time in x:
                y.append(entertime.count(time))
        elif which == 'exit':
            for time in x:
                y.append(exittime.count(time))
        elif which == 'deployed':
            deployed = 0
            for time in x:
                deployed += entertime.count(time)
                deployed -= exittime.count(time)
                y.append(deployed)

        if action == 'plot':
            self.plot(x, y, 'Number of %s (%s)' %(prototype, which))
        elif action == 'export':
            self.export(x, y, '%s_%s.csv' %(prototype, which))


    def timeseries_window(self):
        self.guide_text = ''
        self.ts_window = Toplevel(self.master)
        self.ts_window.title('Timeseries Window')
        self.ts_window.geometry('+700+1000')
        parent = self.ts_window

        tables = self.cur.execute('SELECT name FROM sqlite_master WHERE type="table"').fetchall()
        timeseries_tables_list = []
        for i in tables:
            if 'TimeSeries' in i['name']:
                timeseries_tables_list.append(i['name'].replace('TimeSeries', ''))
        timeseries_tables_list.sort()
        if len(tables) > self.scroll_limit:
            parent = self.add_scrollbar(self.ts_window)

        columnspan = 2
        Label(parent, text='List of Timeseries').grid(row=0, columnspan=columnspan)
        Label(parent, text='======================').grid(row=1, columns=columnspan)
        row = 2

        for i in timeseries_tables_list:
            Label(parent, text=i).grid(row=row, column=0)
            Button(parent, text='more', command=lambda timeseries=i: self.timeseries_action(timeseries)).grid(row=row, column=1)
            row += 1

    def timeseries_action(self, timeseries):
        agentid_list_q = self.cur.execute('SELECT distinct agentid FROM TimeSeries%s' %timeseries).fetchall()
        agentid_list = [i['agentid'] for i in agentid_list_q]
        agentname_list = [self.id_proto_dict[i] for i in agentid_list]
        self.ta_window = Toplevel(self.ts_window)
        self.ta_window.title('%s Timeseries Window' %timeseries.capitalize())
        self.ta_window.geometry('+1000+1000')
        parent = self.ta_window

        if len(agentname_list) > self.scroll_limit:
            parent = self.add_scrollbar(self.ta_window)
        
        columnspan = 3
        Label(parent, text='Agents that reported %s' %timeseries).grid(row=0, columnspan=columnspan)
        Label(parent, text='======================').grid(row=1, columns=columnspan)
        row = 2
        Label(parent, text='Aggregate sum').grid(row=row, column=0)
        Button(parent, text='plot', command=lambda timeseries=timeseries, agentid='agg', action='plot': self.timeseries_action_action(timeseries, agentid, action)).grid(row=row, column=1)
        Button(parent, text='export', command=lambda timeseries=timeseries, agentid='agg', action='export': self.timeseries_action_action(timeseries, agentid, action)).grid(row=row, column=2)
        row = 3
        for indx, i in enumerate(agentname_list):
            Label(parent, text='%s (%s)' %(i, agentid_list[indx])).grid(row=row, column=0)
            Button(parent, text='plot', command=lambda timeseries=timeseries, agentid=agentid_list[indx], action='plot': self.timeseries_action_action(timeseries, agentid, action)).grid(row=row, column=1)
            Button(parent, text='export', command=lambda timeseries=timeseries, agentid=agentid_list[indx], action='export': self.timeseries_action_action(timeseries, agentid, action)).grid(row=row, column=2)
            row += 1
            
       
    def timeseries_action_action(self, timeseries, agentid, action):
        if agentid == 'agg':
            series_q = self.cur.execute('SELECT time, sum(value) FROM TimeSeries%s GROUP BY time' %timeseries).fetchall()
        else:
            series_q = self.cur.execute('SELECT time, sum(value) FROM TimeSeries%s WHERE agentid=%s GROUP BY time' %(timeseries, str(agentid))).fetchall()
        x, y = self.query_result_to_timeseries(series_q, 'sum(value)')

        if action == 'plot':
            self.plot(x, y, '%s Timeseries' %timeseries)
        elif action == 'export':
            if agentid == 'agg':
                name = '%s_aggregate_timeseries.csv' % timeseries
            else:
                name = '%s_%s_timeseries.csv' %(self.id_proto_dict[agentid], timeseries)
            self.export(x, y, name)


    def facility_inventory_window(self):
        # check if explicit inventory is okay

        isit = self.cur.execute('SELECT * FROM InfoExplicitInv').fetchone()
        if not isit['RecordInventory']:
            messagebox.showerror('Dont have it', 'This simulation was run without `explicit_inventory` turned on in the simulation definition. Turn that on and run the simulation again to view the inventory.')
            return

        self.guide_text = ''
        # show material trade between prototypes
        self.inv_window = Toplevel(self.master)
        self.inv_window.title('Which Selection')
        self.inv_window.geometry('+700+1000')
        parent = self.inv_window
        Label(parent, text='Group by agent or prototype:').pack()
        Button(parent, text='Group by agent', command=lambda: self.inv_inv_window(groupby='agent')).pack()
        Button(parent, text='Group by prototype', command=lambda: self.inv_inv_window(groupby='prototype')).pack()

    def inv_inv_window(self, groupby):
        self.guide_text = ''
        # show material trade between prototypes
        self.inv_inv_window = Toplevel(self.inv_window)
        self.inv_inv_window.title('Groupby %s' %groupby)
        self.inv_inv_window.geometry('+1000+1000')
        parent = self.inv_inv_window
        if groupby == 'agent':
            # show the list of all agents to display
            if len(self.id_proto_dict.keys()) > self.view_hard_limit:
                messagebox.showinfo('Too much', 'You have %s distinct agents.. Too much for me to display' %str(len(self.id_proto_dict.keys())))
                self.inv_inv_window.destroy()
                return
            if len(self.id_proto_dict.keys()) > self.scroll_limit:
                parent = self.add_scrollbar(self.inv_inv_window)
            row = 0
            for id_, proto_ in self.id_proto_dict.items():
                Label(parent, text= '%s (%s)' %(proto_, id_)).grid(row=row, column=0)
                Button(parent, text='plot', command=lambda id_list=[id_]: self.inv_action(id_list, 'plot')).grid(row=row, column=1)
                Button(parent, text='export', command=lambda id_list=[id_]: self.inv_action(id_list, 'export')).grid(row=row, column=2)
        
        elif groupby == 'prototype':
            # show the list of prototypes to display
            entry = self.cur.execute('SELECT DISTINCT prototype FROM agententry WHERE kind="Facility"').fetchall()
            proto_list = [i['prototype'] for i in entry]
            proto_list.sort(key=str.lower)
            if len(self.id_proto_dict.keys()) > self.view_hard_limit:
                messagebox.showinfo('Too much', 'You have %s distinct agents.. Too much for me to display' %str(len(proto_list)))
                self.inv_inv_window.destroy()
                return
            if len(proto_list) > self.scroll_limit:
                parent = self.add_scrollbar(self.inv_inv_window)
            row = 0
            for i in proto_list:
                id_list = [k for k,v in self.id_proto_dict.items() if v == i]
                Label(parent, text= '%s' %i).grid(row=row, column=0)
                Button(parent, text='plot', command=lambda id_list=[id_list]: self.inv_action(id_list, 'plot')).grid(row=row, column=1)
                Button(parent, text='export', command=lambda id_list=[id_list]: self.inv_action(id_list, 'export')).grid(row=row, column=2)


    def inv_action(self, id_list, action):
        str_id_list = [str(q) for q in id_list]
        query = 'SELECT sum(quantity), time FROM ExplicitInventory WHERE (agentid = ' + ' OR agentid = '.join(str_id_list) + ') GROUP BY time'
        x, y = self.query_result_to_timeseries(query, 'sum(quantity)')


    # helper functions

    def plot(self, x, y, ylabel, xlabel='Date'):
        fig = plt.figure()
        ax1 = fig.add_subplot(111)
        ax2 = ax1.twiny()
        if type(y) is dict:
            for key, val in y.items():
                ax1.plot(self.timestep_to_date(x), val, label=key)
            plt.legend()
            if sum(sum(y[k]) for k in y) > 1e3:
                ax1 = plt.gca()
                ax1.get_yaxis().set_major_formatter(
                    plt.FuncFormatter(lambda x, loc: "{:,}".format(int(x))))
        else:
            ax1.plot(self.timestep_to_date(x), y)
            if max(y) > 1e3:
                ax1 = plt.gca()
                ax1.get_yaxis().set_major_formatter(
                    plt.FuncFormatter(lambda x, loc: "{:,}".format(int(x))))
        ax1.set_xlabel(xlabel)
        new_tick_locations = np.array([.1, .3, .5, .7, .9])
        ax2.set_xticks(new_tick_locations)
        l = new_tick_locations * max(x)
        l = ['%.0f' %z for z in l]
        print(l)
        ax2.set_xticklabels(l)
        ax2.set_xlabel('Timesteps')
        plt.ylabel(ylabel)
        plt.grid()
        plt.tight_layout()
        plt.show()


    def export(self, x, y, filename):
        export_dir = os.path.join(self.output_path, 'exported_csv')
        if not os.path.exists(export_dir):
            os.mkdir(export_dir)
        filename = os.path.join(export_dir, filename)
        if type(y) is dict:
            s = 'time, %s\n' %', '.join(list(y.keys()))
            for indx, val in enumerate(x):
                s += '%s, %s\n' %(str(x[indx]), ', '.join([q[indx] for q in list(y.values())]))
        else:
            s = 'time, quantity\n'
            for indx, val in enumerate(x):
                s += '%s, %s\n' %(str(x[indx]), str(y[indx]))
        with open(filename, 'w') as f:
            f.write(s)
        print('Exported %s' %filename)
        messagebox.showinfo('Success', 'Exported %s' %filename)


    def timestep_to_date(self, timestep):
        timestep = np.array(timestep) 
        month = self.init_month + (timestep * (self.dt / 2629846))
        year = self.init_year + month//12
        month = month%12
        dates = [x+(y/12) for x, y in zip(year, month)]
        return dates


    def query_result_to_timeseries(self, query_result, col_name, time_col_name='time'):
        x = np.arange(self.duration)
        y = np.zeros(self.duration)
        for i in query_result:
            y[int(i[time_col_name])] += i[col_name]
        return x, y

    def query_result_to_dict(self, query_result, col_name_list, time_col_name='time'):
        x = np.arange(self.duration)
        y = {}
        for i in col_name_list:
            y[i] = np.zeros(self.duration)
        for i in query_result:
            for j in col_name_list:
                y[int(i[time_col_name])] += i[j]
        return x, y


    def aggregate_dates(self, x, y, agg_dt):
        # roughly aggregates
        groups = int(self.agg_dt / self.dt)
        new_x = np.arange(self.duration / groups)
        new_y = []


    def assess_scroll_deny(self, length, window_obj):
        if length > self.view_hard_limit:
            messagebox.showinfo('Too much', 'You have %s distinct values. Too much to show here.' %length)
            window_obj.destroy()
            return -1
        if length > self.scroll_limit:
            return self.add_scrollbar(window_obj)


    def add_scrollbar(self, window_obj):
        canvas = Canvas(window_obj, width=600, height=1000)
        frame = Frame(canvas)
        scrollbar = Scrollbar(window_obj, command=canvas.yview)
        scrollbar.pack(side=RIGHT, fill='y')
        canvas.pack(side=LEFT, fill='both', expand=True)        
        def on_configure(event):
            canvas.configure(scrollregion=canvas.bbox('all'))
        canvas.configure(yscrollcommand=scrollbar.set)
        frame.bind('<Configure>', on_configure)
        canvas.create_window((4,4), window=frame, anchor='nw')
        return frame

    
    def guide(self):
        self.guide_window = Toplevel(self.master)
        self.guide_window.title('Backend Analysis Guide')
        self.guide_window.geometry('+0+400')
        self.guide_text = """
        Here you can perform backend analysis of the Cyclus run.

        For more advanced users, you can navigate the tables yourself,
        using a sql query.

        For more beginner-level users, you can use the get material
        flow to obtain material flow, composition, etc for between
        facilities.

        """

        Label(self.guide_window, textvariable=self.guide_text, justify=LEFT).pack(padx=30, pady=30)
