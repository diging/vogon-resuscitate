
/******************************************************************************
  *         Resources!
  *****************************************************************************/

// Function to get the value of a cookie by its name
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
      const cookies = document.cookie.split(';');
      for (let i = 0; i < cookies.length; i++) {
        const cookie = cookies[i].trim();
        // Check if this cookie's name matches the one we're looking for
        if (cookie.substring(0, name.length + 1) === (name + '=')) {
          cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
          break;
        }
      }
    }
    return cookieValue;
  }

Vue.http.headers.common['X-CSRFToken'] = getCookie('csrftoken');


var Appellation = Vue.resource(BASE_URL + '/rest/appellation{/id}');
var DateAppellation = Vue.resource(BASE_URL + '/rest/dateappellation{/id}');
var Relation = Vue.resource(BASE_URL + '/rest/relationset{/id}');
var Concept = Vue.resource(BASE_URL + '/rest/concept{/id}', {}, {
    search: {method: 'GET', url: BASE_URL + '/rest/concept/search'}
});
var RelationTemplateResource = Vue.resource(BASE_URL + '/relationtemplate{/id}/', {}, {
    create: {method: 'POST', url: BASE_URL + '/relationtemplate{/id}/create/'},
    text: {method: 'POST', url: BASE_URL + '/relationtemplate{/id}/create/text/'},
    get_single_relation: {method: 'GET', url: BASE_URL + '/rest/templates/get_single_relation/'},
});
var ConceptType = Vue.resource(BASE_URL + '/rest/type{/id}');
