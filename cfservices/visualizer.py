# -------------------------------------------------------------------------------
# Copyright IBM Corp. 2017
# 
# Licensed under the Apache License, Version 2.0 (the 'License');
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# 
# http://www.apache.org/licenses/LICENSE-2.0
# 
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an 'AS IS' BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# -------------------------------------------------------------------------------
from pixiedust.display.app import *
import json
import requests

@PixieApp
@Logger()
class Visualizer():
    
    def setup(self):
        '''
        Initialize the app
        '''

        self.debug("Entering method setup")
        
        self.services_df = self.pixieapp_entity.get('data', None)
        if self.services_df is None:
            raise Exception("You must specify a Pandas DataFrame: {'data': <populated DataFrame>}")

        # in case any service name lookups or service plan name lookups failed, replace None with a descriptive meta string 
        self.services_df = self.services_df.fillna(value={'service_plan_name':'[UNKNOWN/DISCONTINUED]', 'service_name':'[UNKNOWN/DISCONTINUED]'})
        
        # pre-compute service type list
        self.service_types_df = self.services_df[['service_guid', 'service_name']].drop_duplicates().sort_values(by=['service_name'])
        
        self.cloud_config = {}

        self.cloud_config['api_base_url'] = self.pixieapp_entity.get('api_base_url', 'https://api.ng.bluemix.net{}')

        if self.pixieapp_entity.get('api_token', None) is None:
        	self.cloud_config['ibmid'] = self.pixieapp_entity.get('ibmid', None)
        	self.cloud_config['password'] = self.pixieapp_entity.get('password', None)
        else:	
        	self.cloud_config['ibmid'] = 'apikey'
        	self.cloud_config['password'] = self.pixieapp_entity.get('api_token')
        
        if self.cloud_config['ibmid'] is None or self.cloud_config['password'] is None:
           raise Exception("You must specify an IBM Cloud user api_token {'api_token': '<token>'} or an {'ibmid': '<ibmid>',  'password': '<password>'}")

        self.cloud_config['credentials'] = None


        response = requests.get(self.cloud_config['api_base_url'].format('/info'))
        if response.status_code == 200:
              auth_endpoint = response.json()['authorization_endpoint'] + '/oauth/token'
              data = 'grant_type=password&username={0}&password={1}'.format(self.cloud_config['ibmid'], self.cloud_config['password'])
              headers = {
                'accept': 'application/json',
                'content-type': 'application/x-www-form-urlencoded;charset=utf-8'
              }
              response = requests.post(auth_endpoint, data=data, headers=headers, auth=('cf', ''))
              if response.status_code == 200:
                 results = response.json()
                 self.cloud_config['credentials'] = results['token_type'] + ' ' + results['access_token']
              else:
                 raise Exception('Fatal error obtaining auth token. IBM Cloud returned {}.'.format(response))
        else:
           raise Exception('Fatal error obtaining auth token. IBM Cloud returned {}.'.format(response))   

        # holds current filter selections
        self.state = {
            'filter': {
                'service_guid': None,
                'service_plan_name': None,
                'org_guid': None,
                'space_guid': None
            }
        }


    
    @route()
    @templateArgs 
    def main_screen(self):
        '''
        Define the UI layout: filters, service instance list and credentials view
        '''
        
        self.debug("Entering method main screen")
        
        # mark all service instances visible by default. filters will override this setting
        self.services_df['hide_service_instance'] = False
        
        return """
            <!-- custom styling -->
            <style>
                div.outer-wrapper {
                    display: table;width:100%;height:100px;
                }
                div.inner-wrapper {
                    display: table-cell;vertical-align: middle;height: 100%;width: 100%;
                }
                th { text-align:center; }
                td { text-align: left; }
            </style>

            <!-- filters -->
            <div class="outer-wrapper" 
                 id="filters{{prefix}}"
                 pd_target="filters{{prefix}}"
                 pd_options="op=display_filters"
                 pd_render_onload
                 class="no_loading_msg">
            </div> 
        
            <!-- service instance list --> 
            <div class="outer-wrapper" 
                 id="matching_service_list{{prefix}}"
                 pd_target="matching_service_list{{prefix}}"
                 pd_options="op=display_service_list"
                 pd_render_onload>
            </div>
        
            <!-- service instance credentials --> 
            <div class="outer-wrapper" 
                 id="credentials_list{{prefix}}"
                 pd_target="credentials_list{{prefix}}"
                 pd_options="op=clear_credentials">

            </div>     
        """

       
    @route(op="display_filters")
    @templateArgs
    def display_filters(self):
        '''
        This PixieApp route refreshes the service, service plan, organization and space filters based on the current state
        '''

        self.info("Entering method display_filters: {} {} {} {}".format(self.state['filter']['service_guid'],
                                                                        self.state['filter']['service_plan_name'],
                                                                        self.state['filter']['org_guid'],
                                                                        self.state['filter']['space_guid']))
        # helpers: temporarily store filter options 
        service_filter_options = {}
        service_plan_filter_options = {}
        org_filter_options = {}
        space_filter_options = {}
    
        for index, row in self.services_df.iterrows():
            service_filter_options[row['service_guid']] = row['service_name']
            if self.state['filter']['service_guid'] is None or self.state['filter']['service_guid'] == row['service_guid']:                
                service_plan_filter_options[row['service_plan_name']] = row['service_plan_name'] 
                if self.state['filter']['service_plan_name'] is None or self.state['filter']['service_plan_name'] == row['service_plan_name']:                
                    org_filter_options[row['org_guid']] = row['org_name']
                    if self.state['filter']['org_guid'] is None or self.state['filter']['org_guid'] == row['org_guid']:                    
                        space_filter_options[row['space_guid']] = row['space_name']                

        # sort filter options using the display name (case-insentitive)
        sorted_service_filter_options_keys = sorted(service_filter_options, key=lambda k: service_filter_options.get(k,'').lower())
        sorted_service_plan_filter_options_keys = sorted(service_plan_filter_options, key=lambda k: service_plan_filter_options.get(k,'').lower())
        sorted_org_filter_options_keys = sorted(org_filter_options, key=lambda k: org_filter_options.get(k,'').lower())
        sorted_space_filter_options_keys = sorted(space_filter_options, key=lambda k: space_filter_options.get(k,'').lower())
        
        # debug
        self.info('Service plan filter options: {}'.format(service_plan_filter_options))
        self.info('Sorted service plan filter option keys: {}'.format(sorted_service_plan_filter_options_keys))
        self.info('Org filter options: {}'.format(org_filter_options))
        self.info('Sorted org filter option keys: {}'.format(sorted_org_filter_options_keys))
        self.info('Space filter options: {}'.format(space_filter_options))
        self.info('Sorted space filter option keys: {}'.format(sorted_space_filter_options_keys))
        
        # render context-sensitive filters
        return  """
            <select id="service_guid_filter{{prefix}}"
                    pd_script="self.reset_selected_service_guid_filter('$val(service_guid_filter{{prefix}})')"
                    pd_refresh="filters{{prefix}},matching_service_list{{prefix}},credentials_list{{prefix}}"
                    class="no_loading_msg">

               <option value="---ALL---">--- All services ---</option>
             {%for filter_option in sorted_service_filter_options_keys %}             
                {% if this['state']['filter']['service_guid'] == filter_option %}
                    <option value="{{filter_option}}" selected>{{service_filter_options[filter_option]}}</option>
                {% else %}
                    <option value="{{filter_option}}">{{service_filter_options[filter_option]}}</option>
                {%endif %} 
             {%endfor%}
            </select>
            
            <select id="service_plan_filter{{prefix}}" 
                    pd_script="self.reset_selected_service_plan_filter('$val(service_plan_filter{{prefix}})')"
                    pd_refresh="filters{{prefix}},matching_service_list{{prefix}},credentials_list{{prefix}}"
                    class="no_loading_msg">
                <option value="---ALL---">--- All service plans ---</option>
            {% for plan_name in sorted_service_plan_filter_options_keys %}
              {% if this['state']['filter']['service_plan_name'] == service_plan_filter_options[plan_name] %}
                <option value="{{service_plan_filter_options[plan_name]}}" selected>{{service_plan_filter_options[plan_name]}}</option>
              {% else %}
                <option value="{{service_plan_filter_options[plan_name]}}">{{service_plan_filter_options[plan_name]}}</option>
              {%endif %}  
            {% endfor %}                             
            </select>
            
            <select id="org_guid_filter{{prefix}}" 
                     pd_script="self.reset_selected_org_guid_filter('$val(org_guid_filter{{prefix}})')"
                     pd_refresh="filters{{prefix}},matching_service_list{{prefix}},credentials_list{{prefix}}"
                     class="no_loading_msg">
               <option value="---ALL---">--- All organizations ---</option>
              {%for filter_option in sorted_org_filter_options_keys %}             
                {% if this['state']['filter']['org_guid'] == filter_option %}
                    <option value="{{filter_option}}" selected>{{org_filter_options[filter_option]}}</option>
                {% else %}
                    <option value="{{filter_option}}">{{org_filter_options[filter_option]}}</option>
                {%endif %} 
             {%endfor%}              
            </select>
            
            <select id="space_guid_filter{{prefix}}"
                    pd_script="self.reset_selected_space_guid_filter('$val(space_guid_filter{{prefix}})')"
                    pd_refresh="filters{{prefix}},matching_service_list{{prefix}},credentials_list{{prefix}}"
                    class="no_loading_msg">
               <option value="---ALL---">--- All spaces ---</option>
              {%for filter_option in sorted_space_filter_options_keys %}             
                {% if this['state']['filter']['space_guid'] == filter_option %}
                    <option value="{{filter_option}}" selected>{{space_filter_options[filter_option]}}</option>
                {% else %}
                    <option value="{{filter_option}}">{{space_filter_options[filter_option]}}</option>
                {%endif %} 
             {%endfor%}                
            </select>        
        """
   
    @route(op="display_service_list")
    @templateArgs
    def display_service_list(self):
        """
        This PixieApp route refreshes the list of service instances that meet the current filter condition
        """
        
        self.info("Entering method display_service_list: {} {} {} {}".format(self.state['filter']['service_guid'],
                                                                      self.state['filter']['service_plan_name'],
                                                                      self.state['filter']['org_guid'],
                                                                      self.state['filter']['space_guid']))
            
        # define filter function
        def filter_df(r, service_guid = None, service_plan_name = None, org_guid = None, space_guid = None):
            """ Return True if this row should be hidden
            """
            if service_guid is not None and service_guid != r['service_guid']:
                return True
            if service_plan_name is not None and service_plan_name != r['service_plan_name']:
                return True
            if org_guid is not None and org_guid != r['org_guid']:
                return True
            if space_guid is not None and space_guid != r['space_guid']:
                return True
            return False
        
        # apply filter function on DataFrame, setting field hide_service_instance to True or False for each row, as appropriate
        self.services_df['hide_service_instance'] = self.services_df.apply(filter_df, 
                                                                           axis = 1, 
                                                                           service_guid = self.state['filter']['service_guid'], 
                                                                           service_plan_name = self.state['filter']['service_plan_name'], 
                                                                           org_guid = self.state['filter']['org_guid'], 
                                                                           space_guid = self.state['filter']['space_guid'])

        # compose list summary message: "Showing X of Y service instances"
        stats = self.services_df.groupby(by='hide_service_instance').size().values
        if len(stats) == 1:
            count_msg = 'Showing {} of {} service instances'.format(stats[0], stats[0])
        else:
            count_msg = 'Showing {} of {} service instances'.format(stats[0], stats[0] + stats[1])
        
        # render list of services that are not marked as hidden
        return  """
         <div>
         {{count_msg}}
         </div>
         <table class="table">
           <thead>
             <tr>
                <th>Service Instance Name</th>
                <th>Service Name</th>
                <th>Service Plan</th>
                <th>Organization</th>
                <th>Space</th>
                <th>Actions</th>
             </tr>
          </thead>
          <tbody>
          {% for row in this.services_df.sort_values(by=['service_instance_name']).itertuples()%}
           {% if row['hide_service_instance'] == False %}
            <tr>
                <td>{{row['service_instance_name']}}</td>
                <td>{{row['service_name']}}</td>
                <td>{{row['service_plan_name']}}</td>
                <td>{{row['org_name']}}</td>
                <td>{{row['space_name']}}</td>
                <td><button class="btn btn-default" type="button" pd_options="service_instance_guid={{row['service_instance_guid']}}" pd_target="credentials_list{{prefix}}">View credentials</button></td>
            </tr>
           {% endif %}
          {% endfor %}
          </tbody>
         </table>
        """
    
        @route(op="clear_credentials")
        def clear_credentials(self):
            return """
            """
    
    
    @route(service_instance_guid="*")
    @templateArgs
    def list_credentials(self, service_instance_guid):
        """
        This PixieApp route retrieves and displays the service credentials for the selected service instance
        """
        
        self.debug("Entering method list_credentials: {}".format(service_instance_guid))
               
        # result data structure
        service_instance_credentials = []
        
        http_headers = {
           'accept':'application/json',
           'content-type':'application/json',
           'authorization':self.cloud_config['credentials'] 
        }
        
        # https://apidocs.cloudfoundry.org/245/service_instances/list_all_service_keys_for_the_service_instance.html
        url = '/v2/service_instances/{}/service_keys'.format(service_instance_guid)  
        while url is not None:
            self.debug('Loading service instance credentials...') 
            response = requests.get(self.cloud_config['api_base_url'].format(url), headers=http_headers)
            if response.status_code == 200:
                for resource in response.json().get('resources', []):
                    service_instance_credentials.append({"name":resource['entity']['name'] , 
                                                         "credentials": resource['entity']['credentials'],
                                                         "formatted_credentials": json.dumps(resource['entity']['credentials'], indent=4)})     
                url = response.json()['next_url']                
            else:
                self.info('Fatal error retrieving service key information: {}'.format(response))
                url = None
 
        # Debug: display credentials
        self.debug(service_instance_credentials)        
        
        svc_instance_metadata = self.services_df[self.services_df['service_instance_guid'] == service_instance_guid].iloc[0]
        instance_info = 'service instance "{}" in org "{}" space "{}"'.format(svc_instance_metadata.get('service_instance_name'),
                                                                              svc_instance_metadata.get('org_name'),
                                                                              svc_instance_metadata.get('space_name'))
        
        if len(service_instance_credentials) == 0:
            return """
            <h3>There are no credentials defined for {{instance_info}}</h3>
            """
        else:     
                     
            # render credentials list 
            return  """
              
              <div>
              <h2>Credentials for {{instance_info}}</h2>
              <ul class="list-group">
              {% for credential in service_instance_credentials %}
                
                <li class="list-group-item">
                
                  <button class="btn btn-default" 
                          type="button">
                    <pd_script>
import json
get_ipython().set_next_input("# @hidden_cell\\n# {}\\n{}={}".format('{{instance_info}}', "credentials", json.dumps({{credential['credentials']}}, indent=4)))
                    </pd_script>
                 Copy "{{credential['name']}}" into notebook cell</button>               
                </li>
                <!-- <div><pre>credentials={{credential['formatted_credentials']}}</pre> -->
              {% endfor %} 
              </ul>
              </div>
              
            """
    
    def reset_selected_service_guid_filter(self, service_guid=None):
        """
        Helper: set service filter to the specified guid and reset all dependent filters
        """
        self.info("Resetting service guid filter and its dependencies to {}".format(service_guid))
        
        if service_guid == '---ALL---':
            # no specific service was selected
            service_guid = None
            
        self.state['filter'] = {
            'service_guid': service_guid,
            'service_plan_name': None,
            'org_guid': None,
            'space_guid': None
        }
        return
    
    def reset_selected_service_plan_filter(self, service_plan_name=None):
        """
        Helper: set service plan filter to the specified name and reset all dependent filters
        """
        self.info("Resetting service plan filter and its dependencies to {}".format(service_plan_name))
        
        if service_plan_name == "---ALL---":
            # no specific service plan was selected
            service_plan_name = None
            
        self.state['filter']['service_plan_name'] = service_plan_name
        self.state['filter']['org_guid'] = None
        self.state['filter']['space_guid'] = None
        return
  
    def reset_selected_org_guid_filter(self, org_guid=None):
        """
        Helper: set Cloud Foundry organization filter to the specified GUID and reset all dependent filters
        """
        self.info("Resetting org guid filter and its dependencies to {}".format(org_guid))
            
        if org_guid == "---ALL---":
            # no specific Cloud Foundry organization was selected
            org_guid = None
        
        self.state['filter']['org_guid'] = org_guid
        self.state['filter']['space_guid'] = None
        return

    def reset_selected_space_guid_filter(self, space_guid=None):
        """
        Helper: set Cloud Foundry space filter to the specified GUID
        """
        self.info("Resetting space guid filter to {}".format(space_guid))
        
        if space_guid == "---ALL---":
            # no specific Cloud Foundry organization was selected
            space_guid = None
            
        self.state['filter']['space_guid'] = space_guid
        return    
    
    