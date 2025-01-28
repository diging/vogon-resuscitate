AppellationDisplayItem = {
    props: ['appellation'],
    template: `<div v-show="appellation.visible && !isDeleted">
                <li v-tooltip="getLabel()"
                    v-show="appellation.visible && !isDeleted"
                    v-on:click="selectAppellation"
                    v-bind:style="{
                        top: position.top,
                        left: position.left,
                        position: 'absolute',
                        width: position.width,
                        height: line_height,
                        'z-index': 2,
                        transition: 'opacity 0.2s ease',
                        opacity: isDeleted ? 0 : 1
                    }"
                    v-bind:class="{
                        'appellation': appellation.interpretation != null,
                        'date-appellation': appellation.dateRepresentation != null,
                        'appellation-selected': appellation.selected
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
                       'z-index': 2
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
                         'z-index': 2
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
            isDeleted: false
        }
    },
    mounted: function () {
        this.updatePosition();
        window.addEventListener('resize', this.updatePosition);
        // Listen for deletion events
        this.$root.$on('appellationDeleted', (deletedAppellation) => {
            if (deletedAppellation.id === this.appellation.id) {
                this.isDeleted = true;
                // Remove from store if it exists
                store.commit('removeAppellation', deletedAppellation);
                // Clear interpretation and selected state
                if (this.appellation.interpretation) {
                    this.appellation.interpretation = null;
                }
                this.appellation.selected = false;
                // Clear from text appellation store
                store.commit('setTextAppellation', []);
            }
        });
    },
    beforeDestroy() {
        // Clean up event listener
        this.$root.$off('appellationDeleted');
    },
    methods: {
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
        selectAppellation: function () {
            this.$emit('selectappellation', this.appellation);
        },
        updatePosition: function () {
            this.mid_lines = [];
            var lineHeight = parseInt(getStyle('text-content', 'line-height'));
            this.position = getTextPosition(this.appellation.position);
            this.line_height = lineHeight - 1;
            var endPoint = getPointPosition(this.appellation.position.endOffset);
            var nLines = 1 + (endPoint.bottom - this.position.bottom) / lineHeight;
            if (nLines > 1) { // The selection may span several lines.
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
            this.$root.$emit('appellationClicked', appellation);
            this.$emit('selectappellation', appellation);
        }
    }
}