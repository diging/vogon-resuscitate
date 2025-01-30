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
            sleep(1500).then(self.updatePosition)
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
                        style="position: fixed; top: 20px; right: 20px; z-index: 1000; 
                               padding: 10px 15px; border-radius: 4px; box-shadow: 0 2px 4px rgba(0,0,0,0.2);">
                       <span class="glyphicon glyphicon-info-sign"></span>
                       Edit Mode: Select new text position 
                       <span class="text-muted">(Press ESC to cancel)</span>
                   </div>
                   <div v-if="showSuccessMessage"
                        class="edit-success-message alert alert-success"
                        style="position: fixed; top: 20px; right: 20px; z-index: 1000;
                               padding: 10px 15px; border-radius: 4px; box-shadow: 0 2px 4px rgba(0,0,0,0.2);">
                       <span class="glyphicon glyphicon-ok"></span>
                       Successfully updated annotation
                   </div>
                   <pre id="text-content"
                        v-on:mouseup="handleMouseup">{{ text }}</pre>
                   <appellation-display
                       v-bind:appellations=appellations
                       v-on:selectappellation="selectAppellation">
                   </appellation-display>
                   <appellation-display
                       v-bind:appellations=dateappellations
                       v-on:selectappellation="selectDateAppellation">
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
            isEditing: false,
            showSuccessMessage: false,
            successMessageTimeout: null
        }
    },
    mounted: function() {
        EventBus.$on('cleartextselection', this.resetTextSelection);
        
        // Listen for edit mode
        EventBus.$on('startEdit', () => {
            this.isEditing = true;
            
            // Add ESC key listener when entering edit mode
            document.addEventListener('keydown', this.handleEscKey);
        });
        
        EventBus.$on('cancelEdit', () => {
            this.isEditing = false;
            localStorage.removeItem('editingAppellation');
            
            // Remove ESC key listener when exiting edit mode
            document.removeEventListener('keydown', this.handleEscKey);
        });
    },
    methods: {
        handleEscKey: function(e) {
            if (e.key === 'Escape' && this.isEditing) {
                EventBus.$emit('cancelEdit');
                this.resetTextSelection();
            }
        },
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
        },
        selectAppellation: function(appellation) { this.$emit('selectappellation', appellation); },
        selectDateAppellation: function(appellation) { this.$emit('selectdateappellation', appellation); },
        textIsSelected: function() { return this.selected.startOffset != null; },
        showTemporarySuccessMessage() {
            // Clear any existing timeout
            if (this.successMessageTimeout) {
                clearTimeout(this.successMessageTimeout);
            }
            
            // Show the message
            this.showSuccessMessage = true;
            
            // Hide after 3 seconds
            this.successMessageTimeout = setTimeout(() => {
                this.showSuccessMessage = false;
            }, 3000);
        },
        handleMouseup: function(e) {
            if (e.target.id != 'text-content') return;
            e.stopPropagation();

            var selection = document.getSelection();
            var startOffset = Math.min(selection.anchorOffset, selection.focusOffset);
            var endOffset = Math.max(selection.anchorOffset, selection.focusOffset);

            if (endOffset == startOffset) return;

            var raw = document.getElementById('text-content').childNodes[0].textContent.slice(startOffset, endOffset);
            this.selected = {
                startOffset: startOffset,
                endOffset: endOffset,
                representation: raw
            }

            if (this.isEditing) {
                const editingAppellation = localStorage.getItem('editingAppellation');
                if (editingAppellation) {
                    const appellation = JSON.parse(editingAppellation);
                    
                    // Update the appellation with new position
                    Appellation.update({ id: appellation.id }, {
                        position: {
                            occursIn: this.text.id,
                            position_type: "CO",
                            position_value: [startOffset, endOffset].join(",")
                        },
                        stringRep: raw,
                        interpretation: appellation.interpretation.uri
                    }).then(response => {
                        // Clear editing state
                        localStorage.removeItem('editingAppellation');
                        this.isEditing = false;
                        
                        // Show success message
                        this.showTemporarySuccessMessage();
                        
                        // Make sure the updated appellation is visible
                        response.body.visible = true;
                        
                        // Update UI
                        this.$root.$emit('appellationUpdated', response.body);
                        
                        // Clear selection
                        EventBus.$emit('cleartextselection');
                        
                        // Force a refresh of all positions
                        this.$nextTick(() => {
                            EventBus.$emit('updatepositions');
                        });
                    }).catch(error => {
                        console.error('Failed to update appellation:', error);
                        alert('Failed to update appellation. Please try again.');
                    });
                }
            } else {
                // Normal text selection handling
                this.$emit('selecttext', this.selected);
            }
            
            clearMouseTextSelection();
        },
    },
    components: {
        'appellation-display': AppellationDisplay,
        'text-selection-display': TextSelectionDisplay
    },
    beforeDestroy() {
        EventBus.$off('cleartextselection');
        EventBus.$off('startEdit');
        EventBus.$off('cancelEdit');
        
        // Clean up ESC key listener
        document.removeEventListener('keydown', this.handleEscKey);
        
        // Clear any pending success message timeout
        if (this.successMessageTimeout) {
            clearTimeout(this.successMessageTimeout);
        }
    }
}
