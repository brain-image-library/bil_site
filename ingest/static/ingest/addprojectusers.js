function add_users() {
    const csrftoken = Cookies.get('csrftoken');
    const project_id = document.getElementById('project_id');
    let output_rows = []
    $('tbody>tr').each(function(i, e){
        let $e = $(e);
        // $e is the tr element
        let user_is_checked = $e.find('#user_is_checked').is(':checked');
        // user_is_checked is a boolean of whether that row is checked or not
             
        if(user_is_checked)
            output_rows.push({
                "user_id": $e.data('user_id'),
                "project_id": project_id.getAttribute('value')
                }
            )
    });
  fetch(`${window.origin}/ingest/write_user_to_project_people/`, {
      method: "POST",
      credentials: "include",
      body: JSON.stringify(output_rows),
      cache: "no-cache",
      headers: new Headers({
          "X-CSRFToken": csrftoken,
          "content-type": "application/json"
      })
  })
      .then(function(response) {
          if (response.status !== 200) {
              console.log('Looks like there was a problem. Status code: ${response.status}');
              return;
          }
              response.json().then(function(data) {
              console.log(data);
              window.location.replace(data['url']);
          });
      })
      .catch(function(error) {
          console.log("Fetch error: " + error);
  });
} 
