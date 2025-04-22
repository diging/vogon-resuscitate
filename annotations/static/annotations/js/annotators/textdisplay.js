TextSelectionDisplay = {
    props: ['selected'],
    template: `<div>
                    <div class="text-selection"
                           v-if="textIsSelected()"
                           v-bind:style="{
                             height: line_height,
                             top: position.top,
                             left: position.left,
                             position: 'absolute',
                             width: position.width,
                             'z-index': 2
                         }">
                    </div>
                    <div class="text-selection"
                         v-if="manyLinesAreSelected()"
                         v-for="line in mid_lines"
                         v-bind:style="{
                           height: line.height,
                           top: line.top,
                           left: line.left,
                           position: 'absolute',
                           width: line.width,
                           'z-index': 2
                       }">
                    </div>
                    <div class="text-selection"
                           v-if="multipleLinesAreSelected()"
                           v-bind:style="{
                             height: line_height,
                             top: end_position.top,
                             left: end_position.left,
                             position: 'absolute',
                             width: end_position.width,
                             'z-index': 2
                         }">
                    </div>
                </div>`,
    mounted: function () {
        window.addEventListener('resize', this.updatePosition);

        // Some activities will shift the text display in ways that invalidate
        //  the calculated position of the overlay.
        self = this;
        EventBus.$on('updateposition', function() {
            sleep(200).then(self.updatePosition)
        });
    },
    data: function() {
        return {
            position: {},
            multi_line: null,
            mid_lines: [],
            end_position: {},
            line_height: 0
        }
    },
    watch: {
        selected: function() { this.updatePosition(); }
    },
    methods: {
        textIsSelected: function() { return this.selected.startOffset != null; },
        multipleLinesAreSelected: function() { return this.end_position.top !== undefined; },
        manyLinesAreSelected: function() { return this.mid_lines.length > 0; },
        updatePosition: function() {
            this.mid_lines = [];
            this.position = getTextPosition(this.selected);
            var endPoint = getPointPosition(this.selected.endOffset);
            var lineHeight = parseInt(getStyle('text-content', 'line-height'));

            this.line_height = lineHeight - 1;  // So that they don't stack.
            var nLines = 1 + (endPoint.bottom - this.position.bottom)/lineHeight;

            if (nLines > 1) {    // The selection may span several lines.
                // clientLeft/clientWidth don't account for inner padding.
                var _padding = parseInt(getStyle('text-content', 'padding'));
                if (!_padding) {    // Firefox.
                    _padding = parseInt(getStyle('text-content', 'paddingLeft'));
                }
                var _left = parseInt(document.getElementById('text-content').clientLeft);
                var _width = parseInt(document.getElementById('text-content').clientWidth);
                var left = _left + _padding;
                var width = _width - (2 * _padding);

                this.end_position = {    // This is the last line, running from
                    top: endPoint.top,   //  far left to the end of the
                    left: left,          //   selection.
                    width: endPoint.right - left
                }

                // If the selection spans more than two lines, we need to
                //  highlight the intermediate lines at full width.
                for (i = 0; i < Math.max(0, nLines - 2); i++) {
                    this.mid_lines.push({
                        top: this.position.top + (i + 1) * lineHeight,
                        left: left,
                        width: width,
                        height: lineHeight - 1
                    })
                }
            } else {
                this.end_position = {};
            }
        }
    }
}


TextDisplay = {
    props: ['appellations', 'dateappellations'],
    template: `<div style="position: relative;">
                   <div v-if="isEditing" 
                        class="edit-mode-message alert alert-info"
                        style="position: fixed; top: 20px; right: 20px; z-index: 1000;">
                       Edit Mode: Select new text position (Press ESC to cancel)
                   </div>
                   <div v-if="listening" 
                        style="position: fixed; 
                               top: 20px; 
                               left: 50%; 
                               transform: translateX(-50%);
                               padding: 10px 20px;
                               background: rgba(0,0,0,0.8);
                               color: white;
                               border-radius: 4px;
                               z-index: 1000;
                               font-size: 14px;">
                       Select text to create an appellation. Press ESC to cancel.
                   </div>
                   <pre id="text-content"
                        v-on:mouseup="handleMouseup">{{ text }}</pre>
                   <appellation-display
                       v-bind:appellations=appellations
                       v-on:selectappellation="selectAppellation"
                       v-on:removeappellation="removeAppellation">
                   </appellation-display>
                   <appellation-display
                       v-bind:appellations=dateappellations
                       v-on:selectappellation="selectDateAppellation"
                       v-on:removeappellation="removeAppellation">
                   </appellation-display>
                   <text-selection-display
                       v-bind:selected=selected></text-selection-display>
                </div>`,
    data: function() {
        return {
            text: TEXT_CONTENT,
            selected: {
                startOffset: null,
                endOffset: null
            },
            selected_position: {
                top: 0,
                left: 0,
                width: 0,
                bottom: 0
            },
            selected_multi_line: false,
            selected_mid_lines: null,
            selected_end_position: null,
            listening: false,
            isEditing: false
        }
    },
    mounted: function() {
        EventBus.$on('cleartextselection', this.resetTextSelection);
        // Add ESC key listener
        window.addEventListener('keyup', this.handleKeyup);
        
        EventBus.$on('startEdit', () => {
            this.isEditing = true;
            document.addEventListener('keydown', this.handleEscKey);
            // Clear any existing selection
            this.resetTextSelection();
        });
        
        EventBus.$on('cancelEdit', () => {
            this.isEditing = false;
            localStorage.removeItem('editingAppellation');
            document.removeEventListener('keydown', this.handleEscKey);
            // Clear any existing selection
            this.resetTextSelection();
        });

        // Reset edit mode and clear selections when a relation is created
        // This ensures the text display component stays in sync with appellation edit states
        // and prevents any lingering selections or edit states after relation creation
        EventBus.$on('resetEditState', () => {
            this.isEditing = false;
            localStorage.removeItem('editingAppellation');
            document.removeEventListener('keydown', this.handleEscKey);
            this.resetTextSelection();
        });
    },
    beforeDestroy: function() {
        // Clean up event listeners
        window.removeEventListener('keyup', this.handleKeyup);
        EventBus.$off('startEdit');
        EventBus.$off('cancelEdit');
        EventBus.$off('resetEditState');
    },
    methods: {
        resetTextSelection: function() {
            this.selected = {
                startOffset: null,
                endOffset: null
            };
            this.selected_position = {
                top: 0,
                left: 0,
                width: 0,
                bottom: 0
            };
            this.selected_multi_line = false;
            this.selected_mid_lines = null;
            this.selected_end_position = null;
            this.listening = false;
        },
        selectAppellation: function(appellation) { this.$emit('selectappellation', appellation); },
        selectDateAppellation: function(appellation) { this.$emit('selectdateappellation', appellation); },
        removeAppellation: function(appellation) {
            // Remove from appellations array
            const index = this.appellations.indexOf(appellation);
            if (index > -1) {
                this.appellations.splice(index, 1);
            }
            // Also check dateappellations if needed
            const dateIndex = this.dateappellations.indexOf(appellation);
            if (dateIndex > -1) {
                this.dateappellations.splice(dateIndex, 1);
            }
        },
        textIsSelected: function() { return this.selected.startOffset != null; },
        handleKeyup: function(e) {
            if (e.key === 'Escape') {
                this.resetTextSelection();
                this.listening = false;
                // Cancel concept selection
                EventBus.$emit('cleartextselection');
                EventBus.$emit('cancelappellation');
                clearMouseTextSelection();
            }
        },
        handleMouseup: function(e) {
            if (!this.isEditing) {
                this.listening = true;
            }

            // We're looking for an event in which the user has selected some text.
            if (e.target.id != 'text-content') return;    // Out of scope.
            e.stopPropagation();

            // Increase the delay for reliable selection capture
            var self = this;
            setTimeout(function() {
                try {
                    // Get the start and end position of the selection
                    var selection = document.getSelection();
                    
                    // Make sure we have a valid selection
                    if (!selection || selection.rangeCount === 0) return;
                    
                    var startOffset = Math.min(selection.anchorOffset, selection.focusOffset);
                    var endOffset = Math.max(selection.anchorOffset, selection.focusOffset);

                    /* 
                     * Validate that actual text is selected:
                     * - If startOffset equals endOffset, no text is selected
                     * - This happens when user just clicks without dragging
                     * - Or when selection collapses to a single point
                     * - Return early to prevent processing empty selections
                     */
                    if (endOffset == startOffset) return;

                    // Get the actual text content node
                    var textContent = document.getElementById('text-content').childNodes[0];
                    if (!textContent) return;
                    
                    var raw = textContent.textContent.slice(startOffset, endOffset);
                    
                    // Ensure we have a non-empty selection
                    if (!raw || raw.trim().length === 0 || 
                        startOffset < 0 || endOffset > textContent.textContent.length) {
                        return;
                    }
                    
                    /* 
                     * Create selection object - this is crucial for position updates
                     * The TextSelectionDisplay component watches this object
                     * and uses it to calculate and update positions
                     */
                    self.selected = {
                        startOffset: startOffset,
                        endOffset: endOffset,
                        representation: raw,
                        timestamp: new Date().getTime()
                    };
                    
                    // Calculate position
                    self.selected_position = getTextPosition(self.selected);
                    
                    // Handle edit mode selection
                    if (self.isEditing) {
                        const editingAppellation = localStorage.getItem('editingAppellation');
                        if (editingAppellation) {
                            const appellation = JSON.parse(editingAppellation);
                            appellation.selected = true;
                            
                            /* 
                             * Update Appellation Position Flow:
                             * 1. Send update to server with:
                             *    - position_value: A comma-separated string of start and end offsets (e.g. "324,435")
                             *      This is the primary source of truth for text position in the database
                             *    - stringRep: The actual selected text content
                             *
                             * 2. When server responds:
                             *    - Parse the position_value string back into numeric offsets
                             *    - Set these on the appellation.position object for frontend use
                             *    - These offsets are used by getTextPosition() from util.js to calculate actual screen coordinates
                             *
                             */
                            Appellation.update({ id: appellation.id }, {
                                position: {
                                    occursIn: appellation.position.occursIn,
                                    position_type: "CO",
                                    position_value: [startOffset, endOffset].join(",")
                                },
                                stringRep: raw,
                                startPos: startOffset,
                                endPos: endOffset,
                                interpretation: appellation.interpretation.uri,
                                project: appellation.project
                            }).then(response => {
                                // Update the position values
                                const updatedAppellation = response.body;
                                const offsets = updatedAppellation.position.position_value.split(',');
                                
                                /*
                                 * We need to maintain two sets of position values for different purposes:
                                 * 
                                 * 1. position.startOffset and position.endOffset:
                                 *    - Used by frontend components for visual rendering, this set is responsible for the highlight on screen
                                 *    - Part of the position object used by getTextPosition() in util.js
                                 *    - These determine where the highlight appears on screen
                                 */
                                updatedAppellation.position.startOffset = parseInt(offsets[0]);
                                updatedAppellation.position.endOffset = parseInt(offsets[1]);
                                
                                /*
                                 * 2. startPos and endPos:
                                 *    - These are old fields from the database model
                                 *    - Still used by some parts of the frontend code
                                 *    - Need to be kept in sync for backwards compatibility (such as submitting quadruples etc)
                                 *    - Direct properties on the appellation object, not in position
                                 */
                                updatedAppellation.startPos = parseInt(offsets[0]);
                                updatedAppellation.endPos = parseInt(offsets[1]);
                                
                                // Clear editing state
                                localStorage.removeItem('editingAppellation');
                                EventBus.$emit('cancelEdit');

                                // Update text selection
                                self.$root.$emit('appellationUpdated', updatedAppellation);
                                
                                self.resetTextSelection();
                                
                                // Show success message
                                EventBus.$emit('showMessage', {
                                    text: 'Successfully updated annotation',
                                    type: 'success'
                                });
                            }).catch(error => {
                                console.error('Failed to update appellation:', error);
                                EventBus.$emit('cancelEdit');
                                EventBus.$emit('showMessage', {
                                    text: 'Failed to update annotation. Please try again.',
                                    type: 'error'
                                });
                            });
                            
                            // Clear selection after update attempt
                            clearMouseTextSelection();
                            return; // Important: don't proceed to normal selection handling
                        }
                    }
                    
                    /*
                     * This is a critical check that prevents unwanted behavior when different modes overlap:
                     * 
                     * 1. When NOT in edit mode (isEditing = false):
                     *    - The condition passes and we emit the 'selecttext' event
                     *    - This starts the process of creating a new appellation with the selected text
                     * 
                     * 2. When IN edit mode (isEditing = true):
                     *    - The condition fails, blocking the 'selecttext' event
                     *    - This prevents accidentally creating a new appellation while trying to update an existing one
                     * 
                     * This serves as a secondary check - even if the early return statement in the edit mode handling 
                     * block above is not triggered (e.g., if no editing appellation was found in localStorage), 
                     * this check still ensures no selection events fire during edit mode.
                     */
                    if (!self.isEditing) {
                        self.$emit('selecttext', self.selected);
                        
                        // Store backup
                        self._lastValidSelection = {
                            startOffset: startOffset,
                            endOffset: endOffset,
                            representation: raw
                        };
                    }
                    
                    clearMouseTextSelection();
                } catch(err) {
                    console.error("Error handling text selection:", err);
                    if (self._lastValidSelection && !self.isEditing) {
                        self.$emit('selecttext', self._lastValidSelection);
                    }
                }
            }, 50);  // Increased delay for more reliable selection capture
        },
        handleEscKey: function(e) {
            if (e.key === 'Escape' && this.isEditing) {
                EventBus.$emit('cancelEdit');
                this.resetTextSelection();
            }
        }
    },
    components: {
        'appellation-display': AppellationDisplay,
        'text-selection-display': TextSelectionDisplay
    }
}