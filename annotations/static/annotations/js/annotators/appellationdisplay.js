AppellationDisplayItem = {
    props: ['appellation'],
    template: `<div v-show="shouldShow">
                <li v-tooltip="getLabel()"
                    v-on:click="selectAppellation"
                    v-bind:style="{
                        top: position.top,
                        left: position.left,
                        position: 'absolute',
                        width: position.width,
                        height: line_height,
                        'z-index': 2,
                        transition: 'all 0.2s ease',
                        opacity: isDeleted ? 0 : (appellation.selected ? 0.5 : 0.3),
                        visibility: shouldShow ? 'visible' : 'hidden',
                        pointerEvents: isDeleted ? 'none' : 'auto'
                    }"
                    v-bind:class="{
                        'appellation': appellation.interpretation != null,
                        'date-appellation': appellation.dateRepresentation != null,
                        'appellation-selected': appellation.selected && !isDeleted
                    }">
                </li>
                <li v-if="manyLinesAreSelected()"
                     v-on:click="selectAppellation"
                     v-for="line in mid_lines"
                     v-tooltip="getLabel()"
                     v-bind:class="{
                         'appellation': appellation.interpretation != null,
                         'date-appellation': appellation.dateRepresentation != null,
                         'appellation-selected': appellation.selected
                     }"
                     v-bind:style="{
                       height: line.height,
                       top: line.top,
                       left: line.left,
                       position: 'absolute',
                       width: line.width,
                       'z-index': 2,
                       opacity: appellation.selected ? 0.5 : 0.3
                   }">
                </li>
                <li v-if="multipleLinesAreSelected()"
                    v-tooltip="getLabel()"
                    v-on:click="selectAppellation"
                    v-bind:style="{
                         height: line_height,
                         top: end_position.top,
                         left: end_position.left,
                         position: 'absolute',
                         width: end_position.width,
                         'z-index': 2,
                         opacity: appellation.selected ? 0.5 : 0.3
                     }"
                     v-bind:class="{
                         'appellation': appellation.interpretation != null,
                         'date-appellation': appellation.dateRepresentation != null,
                         'appellation-selected': appellation.selected
                     }">
                </li>
                </div>`,
    data: function () {
        return {
            position: {
                top: 0,
                left: 0,
                width: 0,
                right: 0,
                bottom: 0
            },
            line_height: 0,
            multi_line: null,
            mid_lines: [],
            end_position: {},
            isDeleted: false,
            cleanupTimeout: null
        }
    },
    computed: {
        shouldShow() {
            return this.appellation.visible && !this.isDeleted;
        }
    },
    watch: {
        'appellation.visible': function(newVal, oldVal) {
            if (!newVal && this.cleanupTimeout) {
                // If visibility is turned off and we're waiting to cleanup,
                // do it immediately
                clearTimeout(this.cleanupTimeout);
                this.cleanupComponent();
            }
        }
    },
    methods: {
        cleanupComponent() {
            // Remove the element from DOM
            if (this.$el && this.$el.parentNode) {
                this.$el.parentNode.removeChild(this.$el);
            }
            this.$destroy();
        },
        
        handleDeletion(deletedAppellation) {
            // Only handle if this is the appellation being deleted
            if (deletedAppellation.id === this.appellation.id) {
                // Immediately remove selection and highlighting
                this.isDeleted = true;
                this.appellation.visible = false;
                this.appellation.selected = false;
                
                // Force remove from DOM immediately for newly created annotations
                if (this.$el && this.$el.parentNode) {
                    this.$el.parentNode.removeChild(this.$el);
                }
                
                // Clear all stores to ensure clean state
                store.commit('removeAppellation', deletedAppellation);
                store.commit('setTextAppellation', []);
                store.commit('resetCreateAppelltionsToText');
                
                // Notify parent components about deselection
                this.$root.$emit('appellationDeselected', this.appellation);
            }
        },
        getLabel: function () {
            if (this.appellation.interpretation) {
                return this.appellation.interpretation.label;
            } else {
                return this.appellation.dateRepresentation;
            }
        },
        multipleLinesAreSelected: function () {
            return this.end_position.top !== undefined;
        },
        manyLinesAreSelected: function () {
            return this.mid_lines.length > 0;
        },
        selectAppellation() {
            if (!this.isDeleted) {
                // Only allow selection if not being deleted
                this.$emit('selectappellation', this.appellation);
            }
        },
        updatePosition: function () {
            this.mid_lines = [];
            var lineHeight = parseInt(getStyle('text-content', 'line-height'));
            this.line_height = lineHeight - 1;

            // Parse position values
            if (this.appellation.position && this.appellation.position.position_value) {
                const [startOffset, endOffset] = this.appellation.position.position_value.split(',').map(Number);
                
                // Get start and end points
                const startPoint = getPointPosition(startOffset);
                const endPoint = getPointPosition(endOffset);
                
                // Update position
                this.position = {
                    top: startPoint.top,
                    left: startPoint.left,
                    width: endPoint.right - startPoint.left,
                    bottom: startPoint.bottom,
                    right: endPoint.right
                };

                var nLines = 1 + (endPoint.bottom - this.position.bottom) / lineHeight;
                if (nLines > 1) {
                    // clientLeft/clientWidth don't account for inner padding.
                    var _padding = parseInt(getStyle('text-content', 'padding'));
                    if (!_padding) { // Firefox.
                        _padding = parseInt(getStyle('text-content', 'paddingLeft'));
                    }
                    var _left = parseInt(document.getElementById('text-content').clientLeft);
                    var _width = parseInt(document.getElementById('text-content').clientWidth);
                    var left = _left + _padding;
                    var width = _width - (2 * _padding);

                    this.end_position = { // This is the last line, running from
                        top: endPoint.top, //  far left to the end of the
                        left: left, //   selection.
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
    },
    mounted() {
        this.updatePosition();
        window.addEventListener('resize', this.updatePosition);
        
        // Listen for deletion events
        this.$root.$on('appellationDeleted', this.handleDeletion);
        // Listen for forced cleanup (e.g., after successful deletion)
        this.$root.$on('forceCleanupAppellation', (id) => {
            if (id === this.appellation.id) {
                this.handleDeletion(this.appellation);
            }
        });
        
        // Listen for appellation updates
        this.$root.$on('appellationUpdated', (updatedAppellation) => {
            if (updatedAppellation.id === this.appellation.id) {
                // Update the appellation data
                Object.assign(this.appellation, updatedAppellation);
                this.appellation.visible = true; // Force visibility
                
                // Force position recalculation
                this.$nextTick(() => {
                    this.updatePosition();
                    // Force another update after a brief delay to ensure rendering
                    setTimeout(() => {
                        this.updatePosition();
                    }, 100);
                });
            }
        });
    },
    beforeDestroy() {
        window.removeEventListener('resize', this.updatePosition);
        this.$root.$off('appellationDeleted', this.handleDeletion);
        this.$root.$off('forceCleanupAppellation');
        this.$root.$off('appellationUpdated');
        if (this.cleanupTimeout) {
            clearTimeout(this.cleanupTimeout);
        }
    }
}


AppellationDisplay = {
    props: ['appellations'],
    template: `<ul>
                <appellation-display-item
                    v-on:selectappellation="selectAppellation"
                    v-bind:appellation=appellation
                    v-for="appellation in current_appellations"></appellation-display-item>
                </ul>`,
    components: {
        'appellation-display-item': AppellationDisplayItem
    },
    data: function () {
        return {
            current_appellations: this.appellations
        }
    },
    mounted() {
        // Listen for appellation updates
        this.$root.$on('appellationUpdated', (updatedAppellation) => {
            const index = this.current_appellations.findIndex(a => a.id === updatedAppellation.id);
            if (index !== -1) {
                // Update the appellation in the list
                Vue.set(this.current_appellations, index, updatedAppellation);
                
                // Force a refresh
                this.$nextTick(() => {
                    EventBus.$emit('updatepositions');
                });
            }
        });
    },
    beforeDestroy() {
        this.$root.$off('appellationUpdated');
    },
    watch: {
        appellations: function (value) {
            // Replace an array prop wholesale doesn't seem to trigger a
            //  DOM update in the v-for binding, but a push() does; so we'll
            //  just push the appellations that aren't already in the array.
            var current_ids = this.current_appellations.map(function (elem) {
                return elem.id;
            });
            var self = this;
            this.appellations.forEach(function (elem) {
                if (current_ids.indexOf(elem.id) < 0) {
                    self.current_appellations.push(elem);
                }
            });
        }
    },
    methods: {
        selectAppellation: function (appellation) {
            this.$emit('selectappellation', appellation);
        },
        // Handle complete removal of appellation from display
        handleDeletedAppellation(appellation) {
            // Remove from current_appellations array
            const index = this.current_appellations.findIndex(a => a.id === appellation.id);
            if (index > -1) {
                // Create new array without the deleted appellation
                const newAppellations = [...this.current_appellations];
                newAppellations.splice(index, 1);
                this.current_appellations = newAppellations;
            }
            
            // Update the parent component's appellations array
            const parentIndex = this.appellations.findIndex(a => a.id === appellation.id);
            if (parentIndex > -1) {
                const newParentAppellations = [...this.appellations];
                newParentAppellations.splice(parentIndex, 1);
                // Emit update to parent
                this.$emit('update:appellations', newParentAppellations);
            }
        }
    }
}