RelationListItem = {
    props: ['relation'],
    template: `<li v-bind:class="{
                        'list-group-item': true,
                        'relation-list-item': true,
                        'relation-disabled': !relation.ready_to_submit
                    }"
                    :title="!relation.ready_to_submit ? 'Not ready for submission' : ''">
                    <span class="pull-right text-muted btn-group">
                        <a class="btn btn-xs" v-on:click="select" :class="{ 'disabled': !relation.ready_to_submit }">
                            <span class="glyphicon glyphicon-hand-down"></span>
                        </a>
                    </span>
                    <div>
                        <input type="checkbox" 
                               v-model="isChecked" 
                               @change="toggleSelection" 
                               :disabled="!relation.ready_to_submit" />
                        {{ getRepresentation(relation) }}
                    </div>
                    <div class="text-warning">Created by <strong>{{ getCreatorName(relation.createdBy) }}</strong> on {{ getFormattedDate(relation.created) }}</div>
                </li>`,

    data() {
        return {
            isChecked: false
        };
    },

    methods: {
        select: function () {
            this.$emit('selectrelation', this.relation);
        },
        isSelected: function () {
            return this.relation.selected;
        },
        getRepresentation: function (relation) {
            if (relation.representation) {
                return relation.representation;
            } else {
                return relation.appellations.map(function (appellation) {
                    return appellation.interpretation.label;
                }).join('; ');
            }
        },
        getCreatorName: function (creator) {
            if (creator.id == USER_ID) {
                return 'you';
            } else {
                return creator.username;
            }
        },
        getFormattedDate: function (isodate) {
            return moment(isodate).format('dddd LL [at] LT');
        },
        toggleSelection() {
            this.$emit('toggleSelection', { relation: this.relation, selected: this.isChecked });
        }
    }
}

RelationList = {
    props: ['relations'],
    template: `<div>
                    <div class="d-flex justify-content-between align-items-center mb-3">
                        <h5>Relations</h5>
                        <button class="btn btn-primary btn-sm" @click="submitSelected" style="margin: 5px;">
                            <i class="glyphicon glyphicon-send"></i>    
                            Submit Selected Quadruples
                        </button>
                    </div>
                    <ul class="list-group relation-list">
                        <relation-list-item
                            v-for="relation in relations"
                            :key="relation.id"
                            :relation="relation"
                            @selectrelation="selectRelation"
                            @toggleSelection="toggleSelection">
                        </relation-list-item>
                    </ul>
                </div>`,
    components: {
        'relation-list-item': RelationListItem
    },
    data() {
        return {
            selectedQuadruples: []
        };
    },
    methods: {
        selectRelation: function (relation) {
            this.$emit('selectrelation', relation);
        },
        toggleSelection({ relation, selected }) {
            if (selected) {
                this.selectedQuadruples.push(relation.id);
            } else {
                this.selectedQuadruples = this.selectedQuadruples.filter(id => id !== relation.id);
            }
        },
        submitSelected() {
            if (this.selectedQuadruples.length === 0) {
                alert("No quadruples selected");
                return;
            }
            // Submit selected quadruples via an API call
            this.selectedQuadruples.forEach((quadrupleId) => {
                this.submitQuadruple(quadrupleId);
            });
        },
        submitQuadruple(quadrupleId) {
            // Replace with your actual submission endpoint or API method
            axios.post(`/api/quadruples/${quadrupleId}/submit/`)
                .then(() => {
                    console.log(`Quadruple ${quadrupleId} submitted successfully`);
                    // Optionally update relation or refresh list after submission
                })
                .catch((error) => {
                    console.error(`Failed to submit quadruple ${quadrupleId}:`, error);
                });
        }
    }
}
