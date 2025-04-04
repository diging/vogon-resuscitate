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
        EventBus.$on('updatepositions', function() {
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
        });
        
        EventBus.$on('cancelEdit', () => {
            this.isEditing = false;
            localStorage.removeItem('editingAppellation');
            document.removeEventListener('keydown', this.handleEscKey);
        });
    },
    beforeDestroy: function() {
        // Clean up event listener
        window.removeEventListener('keyup', this.handleKeyup); 
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
                    
                    // Create selection object
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
                            
                            // Update the appellation with new position
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
                                // Update the position values in the response
                                const updatedAppellation = response.body;
                                const offsets = updatedAppellation.position.position_value.split(',');
                                updatedAppellation.position.startOffset = parseInt(offsets[0]);
                                updatedAppellation.position.endOffset = parseInt(offsets[1]);
                                
                                // Clear editing state
                                localStorage.removeItem('editingAppellation');
                                self.isEditing = false;
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

                    // Normal text selection handling (only if not in edit mode)
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