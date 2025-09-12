/*
Copyright © 2025 Sid Ahmed KHETTAB

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/agpl-3.0.html>.
*/

$(document).ready(function() {

            


            let clickEnabled = false;
            let taggingEnabled = false;
            let tags = []; // Define the tags variable globally
            let highlightsList = [];
            let successCalled = false;
            const projectName = getUrlParameter('project_name');


            // Function to append highlights to the div with id 'Highlights'
            function appendHighlightsToMenu(highlights) {
                // Select the div with id 'Highlights'
                var $highlightsDiv = $('#Highlights');

                // Loop over each highlight group
                $.each(highlights, function(name, highlightsArray) {
                    // Create a container for the group of highlights
                    var $highlightItem = $('<div>').addClass('highlight-item').append(
                        $('<a>').attr('href', '#').text(name), // Create a link for the highlight name
                        $('<button>').addClass('edit-button').text('Edit').data('name', name).data('description', highlightsArray[0].description || '') // Create an edit button with data attributes
                    );

                    // Append the highlight item to the highlights div
                    $highlightsDiv.append($highlightItem);
                });
            }

            // Function to show the popup edit box
            function showPopupEdit(name, description) {
                $('#highlight-name').val(name);
                $('#highlight-description').val(description);
                $('.popup-edit-overlay').show();
                $('.popup-edit-box').show();
            }

            // Function to hide the popup edit box
            function hidePopupEdit() {
                $('.popup-edit-overlay').hide();
                $('.popup-edit-box').hide();
            }

            // Call the function to append highlights
            appendHighlightsToMenu(highlightsData);

            // Event listener for edit button click
            $('#Highlights').on('click', '.edit-button', function() {
                var name = $(this).data('name');
                var description = $(this).data('description');
                showPopupEdit(name, description);
                // Store the original name in a data attribute for reference during save/delete
                $('.save-button').data('original-name', name);
                $('.delete-button').data('original-name', name);
            });

            // Event listener for close button click
            $('.close-button').click(function() {
                hidePopupEdit();
            });

            // AJAX function to save the highlight
            function saveHighlight(originalName, newName, newDescription) {


                $.ajax({
                    url: '/save_highlight',  // URL for Flask route to handle save
                    type: 'POST',
                    contentType: 'application/json',
                    data: JSON.stringify({
                        original_name: originalName,
                        new_name: newName,
                        new_description: newDescription,
                        project_name: projectName
                    }),
                    success: function(response) {
                        hidePopupEdit();
                        // alert('Highlight saved successfully!');
                        // Optionally, update the UI based on the response
                    },
                    error: function(xhr, status, error) {
                        console.error('Error saving highlight:', error);
                        Swal.fire('Error', 'Error saving highlight. Please try again.', 'error');
                    }
                });
            }

            // AJAX function to delete the highlight
            function deleteHighlight(name) {

                $.ajax({
                    url: '/delete_highlight',  // URL for Flask route to handle delete
                    type: 'POST',
                    contentType: 'application/json',
                    data: JSON.stringify({ name: name, project_name: projectName }),
                    success: function(response) {
                        hidePopupEdit();
                        Swal.fire('Deleted', 'Highlight deleted successfully!', 'success');
                        // Optionally, update the UI based on the response
                    },
                    error: function(error) {
                        console.error('Error deleting highlight:', error);
                        Swal.fire('Error', 'Error deleting highlight. Please try again.', 'error');
                    }
                });
            }

            // Event listener for save button click
            $('.save-button').click(function() {
                var originalName = $(this).data('original-name');
                var newName = $('#highlight-name').val();
                var newDescription = $('#highlight-description').val();
                saveHighlight(originalName, newName, newDescription);
            });

            // Event listener for delete button click
            $('.delete-button').click(function() {
                var name = $(this).data('original-name');
                deleteHighlight(name);
            });

            // Hide popup when clicking outside of it
            $('.popup-edit-overlay').click(function() {
                hidePopupEdit();
            });


            // Hide the genreclass div when the hide link is clicked
            $('#hide-link').click(function (e) {
                e.preventDefault(); // Prevent the default action of the link
                $('#genreclass').slideToggle('slow', function() {
                    if ($('#genreclass').is(':visible')) {
                        $('#hide-link').text('[hide]');
                    } else {
                        $('#hide-link').text('[show]');
                    }
                });
            });

            //console.log("The Highlights are: " + JSON.stringify(wrongData[0], null, 2));



            /**
             * Section for handling click and highlight functionality toggling,
             * concatenating elements with specific styling, handling element click events,
             * managing morphology data display, and initializing event handlers.
             */

            // Function to toggle click and highlight functionality
            function toggleClickHighlight() {
                clickEnabled = $('#toggle-click').is(':checked');
                if (!clickEnabled) {
                    disableClickHighlight();
                } else {
                    enableClickHighlight();
                }
            }

            // Disable click and highlight functionality
            function disableClickHighlight() {
                $('span').removeClass('highlight clickable taggable').addClass('non-clickable');
                $('#wrong_morphology_table, #correct_morphology_table, #diff_morphology_table').hide();
                $('#toggle-tagging').prop('checked', false).prop('disabled', true);
                $('#analysisType').hide();
            }

            // Enable click and highlight functionality
            function enableClickHighlight() {
                $('span').removeClass('non-clickable').addClass('clickable');
                $('#toggle-tagging').prop('disabled', false);
                $('#analysisType').show();
            }

            // Function to toggle tagging functionality
            function toggleTagging() {
                taggingEnabled = $('#toggle-tagging').is(':checked');
                if (!taggingEnabled) {
                    disableTagging();
                } else if (clickEnabled) {
                    enableTagging();
                }
            }

            // Disable tagging functionality
            function disableTagging() {
                $('span').removeClass('taggable').addClass('non-taggable');
            }

            // Enable tagging functionality
            function enableTagging() {
                $('span').removeClass('non-taggable').addClass('taggable');
            }

            // Function to concatenate "element" fields with styling based on "operation"
            function concatenateElements(data, type) {
                let concatenatedText = '';

                data.forEach((item, index) => {
                    let additionalAttributes = `data-index="${index}" data-type="${type}" data-pair-id="${item.pair_id}" data-pos-wrong="${item.position_in_wrong}" data-pos-correct="${item.position_in_correct}" data-pos-diff="${item.position_in_diff}" class="non-clickable"`;
                    let operationClass = getOperationClass(item.operation);
                    concatenatedText += `<span class="${operationClass} operations" ${additionalAttributes}>${item.element}</span>`;
                });

                return concatenatedText;
            }

            // Function to get the class based on the operation type
            function getOperationClass(operation) {
                switch (operation) {
                    case 'deleted':
                        return 'deleted';
                    case 'replaced':
                        return 'replaced';
                    case 'added':
                        return 'added';
                    case 'replacedby':
                        return 'replacedby';
                    case 'unchanged':
                        return 'unchanged';
                    default:
                        return '';
                }
            }

            // Event handler for click events on elements
            function handleElementClick(event) {
                if (!clickEnabled) return;

                const element = $(this);

                if (taggingEnabled && element.hasClass('taggable') &&
                    (element.hasClass('unchanged') || element.hasClass('deleted') || element.hasClass('added') || element.hasClass('replaced') || element.hasClass('replacedby'))) {

                    showTaggingPopup(event.clientX + 10, event.clientY + 10, element);
                }

                const posWrong = element.data('pos-wrong');
                const posCorrect = element.data('pos-correct');
                const posDiff = element.data('pos-diff');
                const PairId = element.data('pair-id');
                const type = element.data('type');
                const index = element.data('index');

                let morphologyData = getNlpData(type, index, "morphology");
                let entitiesData = getNlpData(type, index, "entities");

                highlightMatchingElements(posWrong, posCorrect, posDiff, PairId);
                displayNlpData(type, morphologyData, entitiesData);
            }

            // Get morphology data based on type and index
            function getNlpData(type, index, nlpType) {
                if (type === 'wrong') {
                    return wrongData[index][nlpType] || [];
                } else if (type === 'correct') {
                    return correctData[index][nlpType] || [];
                } else if (type === 'diff') {
                    return diffData[index][nlpType] || [];
                }
                return [];
            }

            // Highlight all matching elements
            function highlightMatchingElements(posWrong, posCorrect, posDiff, PairId) {
                $('span').removeClass('highlight');
                $(`span[data-pos-wrong="${posWrong}"][data-pos-correct="${posCorrect}"][data-pos-diff="${posDiff}"][data-pair-id="${PairId}"]`).addClass('highlight');
            }

            // Display morphology data in a table
            function displayNlpData(type, morphologyData, entitiesData) {

                showSelectedTable()

                handleAnalysisTypeChange()

                function showTable(type, data, title) {
                    if (data.length > 0) {
                        const headers = getTableHeaders(data[0][0], title);
                        const theadHTML = createTableHead(headers);
                        const tbodyHTML = createTableBody(headers, data[0]);

                        const tableHTML = `
                            <div class="analysis_table">
                                <h2 style="text-align:center">${title}</h2>
                                <table id="analysis_table_content">
                                    <thead>${theadHTML}</thead>
                                    <tbody>${tbodyHTML}</tbody>
                                </table>
                            </div>
                        `;

                        displayTable(type, tableHTML);
                    } else {
                        hideAllTables();
                    }
                }

                // Function to show the table based on the selected dropdown value
                function showSelectedTable() {
                    const selectedType = $('#analysisType').val();
                    if (selectedType === 'morphological') {
                        showTable(type, morphologyData, 'Morphological Analysis');
                    } else if (selectedType === 'entity') {
                        showTable(type, entitiesData, 'Entity Analysis');
                    }
                }

                function handleAnalysisTypeChange() {
                    // Handle the change event of the dropdown
                    $('#analysisType').change(function () {
                        const selectedType = $(this).val();
                        if (selectedType === 'morphological') {
                            showTable(type, morphologyData, 'Morphological Analysis');
                        } else if (selectedType === 'entity') {
                            showTable(type, entitiesData, 'Entity Analysis');
                        }
                    });
                }

                function displayTable(type, tableHTML) {
                    if (type === 'wrong') {
                        $('#wrong_morphology_table').html(tableHTML).show();
                        $('#correct_morphology_table, #diff_morphology_table').hide();
                    } else if (type === 'correct') {
                        $('#correct_morphology_table').html(tableHTML).show();
                        $('#wrong_morphology_table, #diff_morphology_table').hide();
                    } else if (type === 'diff') {
                        $('#diff_morphology_table').html(tableHTML).show();
                        $('#wrong_morphology_table, #correct_morphology_table').hide();
                    }
                }

                function hideAllTables() {
                    $('#wrong_morphology_table, #correct_morphology_table, #diff_morphology_table').hide();
                }
            }

            // Get table headers, prioritizing important headers
            function getTableHeaders(firstRow, title) {
                let headers = Object.keys(firstRow);
                let importantHeaders;

                // Columns to be deleted
                const columnsToDelete = ['id', 'pair_id', 'position', 'distance'];

                // Remove the specified columns
                headers = headers.filter(header => !columnsToDelete.includes(header));

                if (title === 'Morphological Analysis') {
                    importantHeaders = ['token', 'lemma', 'label', 'tag', 'gender', 'number'];
                } else if (title === 'Entity Analysis') {
                    importantHeaders = ['name', 'content', 'common_or_proper', 'type'];
                } else {
                    importantHeaders = []; // Default or fallback headers
                }

                headers = headers.filter(header => !importantHeaders.includes(header));
                headers.unshift(...importantHeaders);
                return headers;
            }

            // Create table head HTML
            function createTableHead(headers) {
                return headers.map(header => `<th>${header}</th>`).join('');
            }

            // Create table body HTML
            function createTableBody(headers, rows) {
                return rows.map(row => {
                    return `<tr>${headers.map(header => `<td>${row[header]}</td>`).join('')}</tr>`;
                }).join('');
            }

            // Initialize click and change event handlers
            function initializeEventHandlers() {
                $('#toggle-click').change(toggleClickHighlight);
                $('#toggle-tagging').change(toggleTagging);
                $('body').on('click', 'span.clickable', handleElementClick);
            }

            try {
                // Concatenate elements for each dataset and display the results
                const concatenatedWrongText = concatenateElements(wrongData, 'wrong');
                $('#result_wrong').html(concatenatedWrongText);

                const concatenatedCorrectText = concatenateElements(correctData, 'correct');
                $('#result_correct').html(concatenatedCorrectText);

                const concatenatedDiffText = concatenateElements(diffData, 'diff');
                $('#result_diff').html(concatenatedDiffText);

                // Initialize event handlers
                initializeEventHandlers();
            } catch (error) {
                console.error('Error parsing JSON data:', error);
            }


            // Event handler for click events on elements with the class 'taggable'
            // When a 'taggable' span is clicked, this function extracts and stores relevant data attributes
            $(document).on('click', 'span.taggable', function() {
                // Extract the text content of the clicked element
                elementText = $(this).text();

                // Extract custom data attributes from the clicked element
                elementType = $(this).data('type'); // Type of the element (e.g., 'wrong', 'correct', 'diff')
                elementPosWrong = $(this).data('pos-wrong'); // Position in 'wrong' dataset
                elementPosCorrect = $(this).data('pos-correct'); // Position in 'correct' dataset
                elementPosDiff = $(this).data('pos-diff'); // Position in 'diff' dataset
                elementDataPairId = $(this).data('pair-id'); // Retrieve the value of the data-pair-id attribute for the clicked element
            });

            /**
             * Section for handling the display of the tagging popup,
             * extracting and appending highlights, creating unique lists of highlights,
             * generating HTML for highlights, and implementing functionality for creating new tags.
             */

            // Function to show the tagging popup
            function showTaggingPopup(x, y, element) {
                const popup = $('#tagging-popup');
                let tagsHtml = '<div class="popup-header"><span class="close-button">&times;</span></div>';

                // Function to extract highlights from data
                function getHighlights(data) {
                    let result = [];
                    data.forEach(item => {
                        let highlights = item.Highlights;
                        let positionInCorrect = item.position_in_correct;
                        let positionInDiff = item.position_in_diff;
                        let positionInWrong = item.position_in_wrong;
                        let pairID = item.pair_id;
                        highlights.forEach(highlight => {
                            result.push({
                                name: highlight.name,
                                active: highlight.active,
                                position_in_correct: positionInCorrect,
                                position_in_diff: positionInDiff,
                                position_in_wrong: positionInWrong,
                                pair_id: pairID
                            });
                        });
                    });
                    return result;
                }

                // Function to append highlights to highlightsList only once
                function appendToHighlightsList(wrongData, correctData, diffData) {
                    if (!successCalled) {
                        highlightsList.push(...getHighlights(wrongData));
                        highlightsList.push(...getHighlights(correctData));
                        highlightsList.push(...getHighlights(diffData));
                        successCalled = true;
                    }
                }

                // Append highlights to highlightsList
                appendToHighlightsList(wrongData, correctData, diffData);

                // Log the highlightsList for debugging
                console.log("THE HIGHLIGHT IS: " + JSON.stringify(highlightsList));

                // Create a unique list of highlights
                let uniqueHighlights = {};
                highlightsList.forEach(highlight => {
                    if (!uniqueHighlights[highlight.name]) {
                        uniqueHighlights[highlight.name] = {
                            name: highlight.name,
                            positions: []
                        };
                    }
                    uniqueHighlights[highlight.name].positions.push({
                        active: highlight.active,
                        position_in_correct: highlight.position_in_correct,
                        position_in_diff: highlight.position_in_diff,
                        position_in_wrong: highlight.position_in_wrong,
                        pair_id: highlight.pair_id
                    });
                });

                let allHighlights = Object.values(uniqueHighlights);

                // Log all highlights for debugging
                console.log("ALL HIGHLIGHTS ARE: " + JSON.stringify(allHighlights));

                // Generate HTML for each highlight
                if (allHighlights.length > 0) {
                    allHighlights.forEach(highlight => {
                        let checkedAttribute = '';
                        highlight.positions.forEach(position => {
                            const posWrongMatch = (position.position_in_wrong === undefined || position.position_in_wrong === null || element.attr('data-pos-wrong') == position.position_in_wrong);
                            const posCorrectMatch = (position.position_in_correct === undefined || position.position_in_correct === null || element.attr('data-pos-correct') == position.position_in_correct);
                            const posDiffMatch = (position.position_in_diff === undefined || position.position_in_diff === null || element.attr('data-pos-diff') == position.position_in_diff);
                            const pairIdMatch = (position.pair_id === undefined || position.pair_id === null || element.attr('data-pair-id') == position.pair_id);

                            if (posWrongMatch && posCorrectMatch && posDiffMatch && pairIdMatch) {
                                if (position.active) {
                                    checkedAttribute = 'checked';
                                }
                            }
                        });

                        tagsHtml += `
                            <div class="highlight-item">
                                <input type="checkbox" id="highlight-${highlight.name}" name="highlights" value="${highlight.name}" ${checkedAttribute}>
                                <label for="highlight-${highlight.name}">${highlight.name}</label>
                            </div>`;
                    });
                }

                // Add create highlight link to the popup HTML
                tagsHtml += `<a href="#" id="create-highlight-link" class="create-highlight-link">Create a Highlight</a>`;
                popup.html(tagsHtml);
                popup.css({ left: x + 'px', top: y + 'px' }).show();

                // Set up event handlers for the popup elements
                $('#create-highlight-link').off('click').on('click', function(event) {
                    event.preventDefault();
                    showNewHighlightPopup(element);
                });

                // Close button functionality
                popup.find('.close-button').off('click').on('click', function() {
                    popup.hide();
                });

                // Checkbox change event handler
                popup.find('input[type="checkbox"]').off('change').on('change', function() {
                    const highlightName = $(this).val();
                    if (this.checked) {
                        highlightActive(highlightName);
                    } else {
                        highlightInactive(highlightName);
                    }
                });
            }

            // Implement the logic to show a popup for creating a new tag

            function showNewHighlightPopup() {
                // This function should create a new popup with fields for tag name and description
                // and a button to save the new tag

                // HTML structure for the new tag popup
                const newTagPopupHtml = `
                    <div id="new-tag-popup" class="popup" style="left: 50%; top: 50%; transform: translate(-50%, -50%); display: block;">
                        <h3>New Tag</h3>
                        <label for="new-tag-name">Tag Name:</label>
                        <input type="text" id="new-tag-name"><br>
                        <label for="new-tag-description">Description:</label>
                        <input type="text" id="new-tag-description"><br>
                        <button id="save-tag">Save & Close</button>
                    </div>
                `;
                // Append the new tag popup HTML to the body of the document
                $('body').append(newTagPopupHtml);

                // Event handler for the "Save & Close" button
                $('#save-tag').off('click').on('click', function() {
                    // Get the values of the tag name and description input fields
                    const name = $('#new-tag-name').val();
                    const description = $('#new-tag-description').val();

                    // If the tag name is provided
                    if (name) {
                        // Add the new tag to the tags array
                        tags.push({
                            name: name,
                            description: description,
                            elementText: elementText,
                            elementType: elementType,
                            elementPosWrong: elementPosWrong,
                            elementPosCorrect: elementPosCorrect,
                            elementPosDiff: elementPosDiff,
                            elementDataPairId: elementDataPairId
                        });
                        // Update the tags in the backend or frontend as needed
                        updateTags(name, description);
                        // Remove the new tag popup after saving
                        $('#new-tag-popup').remove();
                    }
                });
            }

            /**
             * Section for handling highlight activation and deactivation, updating tags,
             * sending data to the server, and updating checkboxes based on server responses.
             */

            // Function to activate a highlight
            function highlightActive(name) {
                const data = {
                    name: name,
                    active: true,
                    elementText: elementText,
                    elementType: elementType,
                    elementPosWrong: elementPosWrong,
                    elementPosCorrect: elementPosCorrect,
                    elementPosDiff: elementPosDiff,
                    elementDataPairId: elementDataPairId
                };

                // Send the data to Flask using AJAX
                sendHighlightData('/update_highlight', data);
            }

            // Function to deactivate a highlight
            function highlightInactive(name) {
                const data = {
                    name: name,
                    active: false,
                    elementText: elementText,
                    elementType: elementType,
                    elementPosWrong: elementPosWrong,
                    elementPosCorrect: elementPosCorrect,
                    elementPosDiff: elementPosDiff,
                    elementDataPairId: elementDataPairId
                };

                console.log("THE DATA IS: " + JSON.stringify(data));

                // Send the data to Flask using AJAX
                sendHighlightData('/update_highlight', data);
            }

            // Function to send highlight data to Flask using AJAX
            function sendHighlightData(url, data) {

                data.project_name = projectName;  // Add project name to data

                $.ajax({
                    url: url,
                    type: 'POST',
                    contentType: 'application/json',
                    data: JSON.stringify(data),
                    success: function(response) {
                        console.log('Highlight data sent successfully:', response);
                        updateCheckboxes(response, false);
                    },
                    error: function(xhr, status, error) {
                        console.error('Error sending highlight data:', error);
                    }
                });
            }

            // Function to update tags
            function updateTags(name, description) {
                const data = {
                    name: name,
                    description: description,
                    elementText: elementText,
                    elementType: elementType,
                    elementPosWrong: elementPosWrong,
                    elementPosCorrect: elementPosCorrect,
                    elementPosDiff: elementPosDiff,
                    elementDataPairId: elementDataPairId
                };

                data.project_name = projectName;  // Add project name to data

                // Send the data to Flask using AJAX
                $.ajax({
                    url: '/update_tags',  // URL of the Flask route
                    type: 'POST',
                    contentType: 'application/json',
                    data: JSON.stringify(data),
                    success: function(response) {
                        console.log('Data sent successfully:', response);
                        updateCheckboxes(response, true);
                    },
                    error: function(xhr, status, error) {
                        console.error('Error sending data:', error);
                    }
                });
            }

            // Function to update checkboxes based on received data
            function updateCheckboxes(response, creation) {
                // Set the flag to indicate that successFunction has been called
                successCalled = true;

                console.log('Response received:', response);
                const updatedHighlights = response.updated_highlights;
                const updatedPosCorrect = response.updated_pos_correct;
                const updatedPosDiff = response.updated_pos_diff;
                const updatedPosWrong = response.updated_pos_wrong;
                const updatedPairId = response.updated_pair_id;

                console.log('Updated positions:', {
                    updatedPosCorrect,
                    updatedPosDiff,
                    updatedPosWrong,
                    updatedPairId
                });

                // Iterate through each highlight and update checkboxes accordingly
                updatedHighlights.forEach(updatedHighlight => {
                    const updatedName = updatedHighlight.name;
                    const updatedActive = updatedHighlight.active;

                    console.log('Processing highlight:', {
                        updatedName,
                        updatedActive
                    });

                    let highlightExists = false;

                    // Check if the highlight already exists in highlightsList
                    highlightsList.forEach((highlight, index) => {
                        if ((highlight.name === updatedName) &&
                            (updatedPosCorrect === null || highlight.position_in_correct === updatedPosCorrect) &&
                            (updatedPosDiff === null || highlight.position_in_diff === updatedPosDiff) &&
                            (updatedPosWrong === null || highlight.position_in_wrong === updatedPosWrong) &&
                            (updatedPairId === null || highlight.pair_id === updatedPairId)) {
                            // Highlight exists, update it
                            highlightsList[index].active = updatedActive;
                            highlightExists = true;

                            // Find the checkbox corresponding to the highlight
                            const checkbox = $(`#highlight-${highlight.name}`);
                            if (checkbox.length) {
                                // Update the checkbox based on the active status
                                checkbox.prop('checked', updatedActive);
                                console.log(`Checkbox for ${highlight.name} set to ${updatedActive}`);
                            }
                        }
                    });

                    if (!highlightExists) {
                        // Highlight does not exist, add it to the list
                        const newHighlight = {
                            name: updatedName,
                            active: updatedActive,
                            position_in_correct: updatedPosCorrect,
                            position_in_diff: updatedPosDiff,
                            position_in_wrong: updatedPosWrong,
                            pair_id: updatedPairId,
                        };
                        highlightsList.push(newHighlight);

                        // Add the highlight name to the popup if the checkbox doesn't exist
                        const newCheckboxHtml = `
                            <div class="highlight-item">
                                <input type="checkbox" id="highlight-${updatedName}" name="highlights" value="${updatedName}" ${updatedActive ? 'checked' : ''}>
                                <label for="highlight-${updatedName}">${updatedName}</label>
                            </div>`;
                        if (creation) {
                            $('#create-highlight-link').before(newCheckboxHtml);
                        }
                        console.log(`Checkbox for ${updatedName} added to the popup`);
                    }
                });
            }

            // Toggle the sidebar and content layout, and switch the icon on the toggle button
            $('.toggle-btn').click(function() {
                // Toggle the 'active' class on the sidebar, which controls its visibility
                $('.sidebar').toggleClass('active');

                // Toggle the 'shifted' class on the content, which adjusts its margin to accommodate the sidebar
                $('.content').toggleClass('shifted');

                // Find the icon within the clicked toggle button and switch between 'fa-bars' and 'fa-times');
            });


            // Function to get URL parameter
            function getUrlParameter(name) {
                name = name.replace(/[[\]/, '\\[').replace(/[\\\]]/, '\\]');
                const regex = new RegExp('[\\?&]' + name + '=([^&#]*)');
                const results = regex.exec(location.search);
                return results === null ? '' : decodeURIComponent(results[1].replace(/\+/g, ' '));
            }


        });




    
