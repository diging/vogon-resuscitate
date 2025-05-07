AppellationDisplayItem = {
    props: ['appellation'],
    template: `<div v-if="appellation.visible">
                <li v-tooltip="getLabel()"
                    v-if="appellation.visible"
                    v-on:click="selectAppellation"
                    v-bind:style="{
                        top: position.top,
                        left: position.left,
                        position: 'absolute',
                        width: position.width,
                        height: line_height,
                        'z-index': 2
                    }"
                    v-bind:class="{
                        'appellation': true,
                        'date-appellation': appellation.dateRepresentation != null,
                        'appellation-selected': isSelected
                    }">
                </li>
                <li v-if="manyLinesAreSelected()"
                     v-on:click="selectAppellation"
                     v-for="line in mid_lines"
                     v-tooltip="getLabel()"
                     v-bind:class="{
                         'appellation': true,
                         'date-appellation': appellation.dateRepresentation != null,
                         'appellation-selected': isSelected
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
                         'appellation': true,
                         'date-appellation': appellation.dateRepresentation != null,
                         'appellation-selected': isSelected
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
            end_position: {}
        }
    },
    computed: {
        isSelected: function() {
            return this.appellation.selected;
        }
    },
    mounted: function () {
        this.updatePosition();
        window.addEventListener('resize', this.updatePosition);

        this.$root.$on('appellationUpdated', (updatedAppellation) => {
            if (this.appellation.id === updatedAppellation.id) {
                // Update the appellation data
                Object.assign(this.appellation, updatedAppellation);
                
                // Ensure the appellation is visible
                this.appellation.visible = true;
                
                // Force a refresh of positions for updated appellation
                this.$nextTick(() => {
                    this.updatePosition();
                    EventBus.$emit('updateposition');
                });
            }
        });
    },
    methods: {
        //  works on a saved Appellation (character offsets that come from
        //  the backend). 
        //  This wrapper forwards the appellation.position to the helper and stores the
        //  returned rectangles in this component's reactive data so the
        //  <li> elements update.
        // -------------------------------------------------------------
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
            if (!this.appellation || !this.appellation.position) {
                return;
            }

            var calc = calculateOverlayPositions(this.appellation.position);
            this.position     = calc.position;
            this.mid_lines    = calc.mid_lines;
            this.end_position = calc.end_position;
            this.line_height  = calc.line_height;
        }
    }
}


AppellationDisplay = {
    props: ['appellations'],
    template: `<ul>
                <appellation-display-item
                    v-on:selectappellation="selectAppellation"
                    v-bind:appellation=appellation
                    v-for="appellation in appellations"
                    :key="appellation.id">
                </appellation-display-item>
                </ul>`,
    components: {
        'appellation-display-item': AppellationDisplayItem
    },
    methods: {
        selectAppellation: function (appellation) {
            this.$root.$emit('appellationClicked', appellation);
            this.$emit('selectappellation', appellation);
        }
    }
}