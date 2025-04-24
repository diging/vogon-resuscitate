var evaluateNodeType = function(elem) {
    var id = elem.attr('id'),
        part = elem.attr('part'),
        name = elem.attr('name'),
        value = elem.val();



    var prefix_parts = name.split('-');
    var prefix = prefix_parts.slice(0, prefix_parts.length - 1).join('-');


    if (value == 'TP') {
        $('#' + prefix + '-' + part + '_type_container').css('display', 'block');
        $('#' + prefix + '-' + part + '_concept_text_container').css('display', 'none');
        $('#' + prefix + '-' + part + '_relationtemplate_internal_id_container').css('display', 'none');
    } else if (value == 'CO') {
        $('#' + prefix + '-' + part + '_type_container').css('display', 'none');
        $('#' + prefix + '-' + part + '_concept_text_container').css('display', 'block');
        $('#id_' + prefix + '-' + part + '_concept_results_elem').css('display', 'block');
        // $('#' + prefix + '-' + part + '_concept_text_container').css('display', 'block');
        $('#' + prefix + '-' + part + '_relationtemplate_internal_id_container').css('display', 'none');
    } else if (value == 'RE') {
        $('#' + prefix + '-' + part + '_type_container').css('display', 'none');
        $('#' + prefix + '-' + part + '_concept_text_container').css('display', 'none');
        $('#' + prefix + '-' + part + '_relationtemplate_internal_id_container').css('display', 'block');

        $('#' + prefix + '-' + part + '_description_container').css('display', 'none');
        $('#' + prefix + '-' + part + '_label_container').css('display', 'none');
        $('#' + prefix + '-' + part + '_prompt_text_container').css('display', 'none');
    } else {
        $('#' + prefix + '-' + part + '_type_container').css('display', 'none');
        $('#' + prefix + '-' + part + '_concept_text_container').css('display', 'none');
        $('#' + prefix + '-' + part + '_relationtemplate_internal_id_container').css('display', 'none');

        $('#' + prefix + '-' + part + '_description_container').css('display', 'none');
        $('#' + prefix + '-' + part + '_label_container').css('display', 'none');
        $('#' + prefix + '-' + part + '_prompt_text_container').css('display', 'none');
    }

    if (value == 'TP' | value == 'CO' | value == 'DT') {
        $('#' + prefix + '-' + part + '_description_container').css('display', 'block');
        $('#' + prefix + '-' + part + '_label_container').css('display', 'block');
        $('#' + prefix + '-' + part + '_prompt_text_container').css('display', 'block');
    }
}


var cloneMore = function(selector, type) {
    var newElement = $(selector).clone(false);
    var total = Number($('#id_parts-TOTAL_FORMS').val());

    newElement.find('div').each(function() {
        var attrs = {};
        if ($(this).attr('id')) {
             attrs['id'] = $(this).attr('id').replace('-' + (total-1) + '-','-' + total + '-');
             attrs['selected-object'] = 'searchStr_' + total;
        }
        if ($(this).attr('name')) {
             attrs['name'] = $(this).attr('name').replace('-' + (total-1) + '-','-' + total + '-');
        }

        $(this).attr(attrs);
    });

    newElement.find(':input').each(function() {
        var attrs = {};
        var elem = $(this);
        if ($(this).attr('ng-model')) {
            attrs['ng-model'] = $(this).attr('ng-model').replace('_' + (total-1) + '_','_' + total + '_');
        }

        Array('id', 'description', 'name', 'target', 'results-target', 'status-target').forEach(function(name) {
            if (elem.attr(name)) {
                attrs[name] = elem.attr(name).replace('-' + (total-1) + '-','-' + total + '-');
            }
        })

        if ($(this).attr('type') == 'checkbox') {   // For prompt-text fields.
            $(this).prop('checked', true);

        }

        if ($(this).attr('concept_id')) {   // For specific concept fields.
            attrs['concept_id'] = '';
        }

        $(this).attr(attrs);

        // Increment internal_id, but avoid messing with the relation_internal_id fields.
        if ($(this).attr('name').indexOf('internal_id') > -1 & $(this).attr('name').indexOf('relation') == -1) {
            $(this).val(total);
        } else {
            // This might be overkill....
            $(this).val('');
            $(this).removeAttr('value');
            $(this).removeProp('value');
        }
    });

    newElement.find('li').each(function() {
        var attrs = {};
        if ($(this).attr('id')) {
            attrs['id'] = $(this).attr('id').split('-' + (total-1) + '-').join('-' + total + '-');
        }
        $(this).attr(attrs);

    })
    newElement.find('label').each(function() {
        if ($(this).attr('for')) {
            var newFor = $(this).attr('for').replace('-' + (total-1) + '-','-' + total + '-');
            $(this).attr('for', newFor);
        }
    });
    newElement.find('#form_ident').each(function() {
        $(this).text(total);
    });

    total++;
    $('#id_parts-TOTAL_FORMS').val(total);

    $('#add_form_row').before(newElement);
    // $scope.relation_options.push(total - 1);

}

var bindTypeField = function() {
    $('.node_type_field').each(function(i, elem) {
        evaluateNodeType($(elem));
    });
    $('.node_type_field').on('change', function() {
        evaluateNodeType($(this));
    });
}

var bindAutocomplete = function(input_elem, pos) {
    var results_elem = $('#' + input_elem.attr('results-target'));
    var status_elem = $('#' + input_elem.attr('status-target'));
    var target = $('#' + input_elem.attr('target'));

    status_elem.removeClass('glyphicon-time');
    status_elem.removeClass('glyphicon-exclamation-sign');
    status_elem.removeClass('glyphicon-ok');
    status_elem.removeClass('glyphicon-hourglass');
    status_elem.addClass('glyphicon-search');
    input_elem.keyup(function() {
        var q = input_elem.val();
        if (searchPromise != null) {
            results_elem.empty();
            clearTimeout(searchPromise);
        }
        status_elem.removeClass('glyphicon-search');
        status_elem.removeClass('glyphicon-exclamation-sign');
        status_elem.removeClass('glyphicon-hourglass');
        status_elem.removeClass('glyphicon-ok');
        status_elem.addClass('glyphicon-time');

        searchPromise = setTimeout(function() {
            status_elem.removeClass('glyphicon-time');
            status_elem.removeClass('glyphicon-search');
            status_elem.removeClass('glyphicon-exclamation-sign');
            status_elem.removeClass('glyphicon-ok');
            status_elem.addClass('glyphicon-hourglass');
            $.get(BASE_URL + "/rest/concept/search", {
                    search: q,
                    pos: pos,
                    remote: true,
                })
                .done(function(response) {
                    status_elem.removeClass('glyphicon-time');
                    status_elem.removeClass('glyphicon-exclamation-sign');
                    status_elem.removeClass('glyphicon-ok');
                    status_elem.removeClass('glyphicon-hourglass');
                    status_elem.addClass('glyphicon-search');
                    response.results.forEach(function(result) {
                        $("<a class='list-group-item' style='cursor: pointer;'>")
                            .click(function() {
                                target.val(result.uri);
                                input_elem.val(result.label);
                                results_elem.empty();
                                searchPromise = null;
                                status_elem.removeClass('glyphicon-time');
                                status_elem.removeClass('glyphicon-search');
                                status_elem.removeClass('glyphicon-hourglass');
                                status_elem.removeClass('glyphicon-exclamation-sign');
                                status_elem.addClass('glyphicon-ok');
                            })
                            .append("" + result.label + "<br><span class='text-muted'>" + result.description + "</span>" )
                            .appendTo(results_elem);
                    });
                })
                .fail(function(xhr, status, error) {
                    console.log(xhr, status, error);
                    status_elem.removeClass('glyphicon-time');
                    status_elem.removeClass('glyphicon-search');
                    status_elem.removeClass('glyphicon-hourglass');
                    status_elem.removeClass('glyphicon-ok');
                    status_elem.addClass('glyphicon-exclamation-sign');
                })
        }, 500)
    })
}

var addRelation = function() {
    // Appends another Relation row, and corresponding formset.
    cloneMore('.form_table_row:last', 'form');
    $('.autocomplete').each(function() {
        var pos = 'noun';
        if (this.id.indexOf('predicate') > -1) {
            pos = 'verb';
        }
        bindAutocomplete($('#' + this.id), pos);
    });
    bindTypeField();
}

bindTypeField();

$('#add-relation-button').on('click', function() {
    addRelation();
})

$('.autocomplete').each(function() {
    var pos = 'noun';
    if (this.id.indexOf('predicate') > -1) {
        pos = 'verb';
    }
    bindAutocomplete($('#' + this.id), pos);
});


var searchPromise = null;

// Initialize both expression and relation nodes fields when the page loads
$(document).ready(function() {
    // Always show both sets of fields
    $('#expression_container').show();
    $('#relation_nodes_container').show();
    
    // Enable all fields - both expression and node fields are required
    $('#first_node_type, #first_node_value, #second_node_type, #second_node_value, #third_node_type, #third_node_value').prop('disabled', false);
    $('#expression_field_container textarea').prop('disabled', false);
    
    // Disable the terminal_nodes field since it's handled by the syncTerminalNodes function
    $('#id_terminal_nodes').prop('disabled', true).css('background-color', '#f0f0f0');
    
    // Add a help note
    if ($('#id_terminal_nodes').parent().find('.terminal-nodes-note').length === 0) {
        $('#id_terminal_nodes').after('<small class="form-text text-muted terminal-nodes-note">Terminal nodes are automatically generated from Node values and expression references.</small>');
    }
    
    // Initialize terminal nodes on page load
    syncTerminalNodes();
    
    // Add event listeners to keep terminal nodes in sync
    $('#first_node_type, #first_node_value, #second_node_type, #second_node_value, #third_node_type, #third_node_value').on('change', syncTerminalNodes);
    $('#expression_field_container textarea').on('input', syncTerminalNodes);
    
    // Function to synchronize terminal nodes with both expression and relation nodes
    function syncTerminalNodes() {
        try {
            // Get the values from inputs
            var firstType = $('#first_node_type').val();
            var firstValue = $('#first_node_value').val();
            
            var secondType = $('#second_node_type').val();
            var secondValue = $('#second_node_value').val();
            
            var thirdType = $('#third_node_type').val();
            var thirdValue = $('#third_node_value').val();
            
            // Extract nodes from expression
            var expression = $('#expression_field_container textarea').val();
            var expressionNodes = [];
            
            // Match patterns like {0s}, {1p}, {2o}, etc.
            var nodePattern = /\{([^\}]+)\}/g;
            var match;
            while ((match = nodePattern.exec(expression)) !== null) {
                expressionNodes.push(match[1]);
            }
            
            // Build terminal nodes from Node type fields
            var terminalNodes = [];
            if (firstType === 'Node' && firstValue) {
                terminalNodes.push(firstValue);
            }
            if (secondType === 'Node' && secondValue) {
                terminalNodes.push(secondValue);
            }
            if (thirdType === 'Node' && thirdValue) {
                terminalNodes.push(thirdValue);
            }
            
            // Combine with expression nodes
            expressionNodes.forEach(function(node) {
                if (terminalNodes.indexOf(node) === -1) {
                    terminalNodes.push(node);
                }
            });
            
            // Only update if we have values to set and they're different from current value
            if (terminalNodes.length > 0) {
                var currentValue = $('#id_terminal_nodes').val();
                var newValue = terminalNodes.join(',');
                
                if (currentValue !== newValue) {
                    $('#id_terminal_nodes').val(newValue);
                }
            }
        } catch (error) {
            console.error('Error in syncTerminalNodes:', error);
        }
    }
    
    // Add form submission handler to validate all fields
    $('form').on('submit', function(e) {
        try {
            // Validate that all required fields are filled
            var allFieldsFilled = true;
            
            // Check all node fields
            var nodeFields = [
                '#first_node_type', '#first_node_value',
                '#second_node_type', '#second_node_value', 
                '#third_node_type', '#third_node_value'
            ];
            
            nodeFields.forEach(function(field) {
                if (!$(field).val()) {
                    allFieldsFilled = false;
                    $(field).addClass('is-invalid');
                } else {
                    $(field).removeClass('is-invalid');
                }
            });
            
            // Check expression field
            if (!$('#expression_field_container textarea').val()) {
                allFieldsFilled = false;
                $('#expression_field_container textarea').addClass('is-invalid');
            } else {
                $('#expression_field_container textarea').removeClass('is-invalid');
            }
            
            if (!allFieldsFilled) {
                e.preventDefault();
                // Show error message
                $('#form-error-message').remove(); // Remove any existing error message
                $('form').prepend('<div id="form-error-message" class="alert alert-danger alert-dismissible fade show" role="alert">Please fill in all required fields<button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button></div>');
                return false;
            }
            
            // Get the values directly from inputs
            var firstType = $('#first_node_type').val();
            var firstValue = $('#first_node_value').val();
            
            var secondType = $('#second_node_type').val();
            var secondValue = $('#second_node_value').val();
            
            var thirdType = $('#third_node_type').val();
            var thirdValue = $('#third_node_value').val();
            
            // Extract nodes from expression
            var expression = $('#expression_field_container textarea').val();
            var expressionNodes = [];
            
            // Match patterns like {0s}, {1p}, {2o}, etc.
            var nodePattern = /\{([^\}]+)\}/g;
            var match;
            while ((match = nodePattern.exec(expression)) !== null) {
                expressionNodes.push(match[1]);
            }
            
            // Build terminal nodes from Node type fields
            var terminalNodes = [];
            if (firstType === 'Node') {
                terminalNodes.push(firstValue);
            }
            if (secondType === 'Node') {
                terminalNodes.push(secondValue);
            }
            if (thirdType === 'Node') {
                terminalNodes.push(thirdValue);
            }
            
            // Combine with expression nodes
            expressionNodes.forEach(function(node) {
                if (terminalNodes.indexOf(node) === -1) {
                    terminalNodes.push(node);
                }
            });
            
            // Check that the user hasn't manually entered incompatible terminal nodes
            var userTerminalNodes = $('#id_terminal_nodes').val().split(',').map(function(s) { return s.trim(); }).filter(Boolean);
            var missingNodes = [];
            
            // Check that all calculated nodes are in the user-entered nodes
            terminalNodes.forEach(function(node) {
                if (userTerminalNodes.indexOf(node) === -1) {
                    missingNodes.push(node);
                }
            });
            
            if (missingNodes.length > 0) {
                // Alert the user about missing nodes and update the field
                alert('Terminal nodes must include all Node values and expression references. Missing: ' + missingNodes.join(', '));
                $('#id_terminal_nodes').val(terminalNodes.join(','));
                e.preventDefault();
                return false;
            }
            
            // Set terminal nodes field to include all needed nodes
            $('#id_terminal_nodes').val(terminalNodes.join(','));
            
            // Re-enable the field for form submission
            $('#id_terminal_nodes').prop('disabled', false);
            
            return true; // Allow form submission to continue
        } catch (error) {
            console.error('Error in form submission handler:', error);
            return true; 
        }
    });
    
    // dynamic validation for node types
    function validateNodeTypes() {
        // Make sure something is selected for each dropdown
        var allSelected = true;
        $('.node-type-dropdown').each(function() {
            if (!$(this).val()) {
                allSelected = false;
            }
        });
        
        if (allSelected) {
            $('.node-type-dropdown').removeClass('is-invalid');
            return true;
        } else {
            // mark empty dropdowns as invalid
            $('.node-type-dropdown').each(function() {
                if (!$(this).val()) {
                    $(this).addClass('is-invalid');
                } else {
                    $(this).removeClass('is-invalid');
                }
            });
            return false;
        }
    }
    
    // Validate on change
    $('.node-type-dropdown').on('change', validateNodeTypes);
    
    // Synchronize node values with terminal nodes
    function updateTerminalNodes() {
        if ($('#use_relation_nodes').is(':checked')) {
            var nodeValues = [];
            
            // Collect all node values (only for Node type, not URI)
            if ($('#first_node_type').val() === 'Node') {
                var value = $('#first_node_value').val();
                if (value) nodeValues.push(value);
            }
            
            if ($('#second_node_type').val() === 'Node') {
                var value = $('#second_node_value').val();
                if (value) nodeValues.push(value);
            }
            
            if ($('#third_node_type').val() === 'Node') {
                var value = $('#third_node_value').val();
                if (value) nodeValues.push(value);
            }
            
            // If we have node values, update the terminal_nodes field
            if (nodeValues.length > 0) {
                $('#id_terminal_nodes').val(nodeValues.join(','));
            } else {
                // Handle case where there are no Node types (all URIs)
                // Set terminal_nodes to a valid empty format
                $('#id_terminal_nodes').val('');
            }
        }
    }
    
    // Update terminal nodes when node values change
    $('#first_node_value, #second_node_value, #third_node_value').on('change keyup', function() {
        updateTerminalNodes();
    });
    
    // Update node fields when their type changes
    $('#first_node_type, #second_node_type, #third_node_type').on('change', function() {
        updateTerminalNodes();
    });
});


// source: function( request, response ) {
//     $(this).addClass('ajax-loading');
//     $.getJSON(BASE_URL + "/rest/concept/search", {
//         search: extractLast( request.term ),
//         pos: pos,
//         remote: true,
//     }, function(data){
//         $(this).removeClass('ajax-loading');
//         response(data.results);
//     } );
// },
